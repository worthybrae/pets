"""Goals (L4): long projects above purposes, as a registry.

A Goal is something Mimo works toward for days: a home of its own, iron tools, a full larder. It
has a name, a title and a why (for the model and the HUD), the goals that must be settled first
(`after`: reached, or complete now), a validity check, a rules score and a thought. Its progress
is a list of Milestones, each with its words, a share from 0 to 1 read from Mimo's state and
memory, and the purposes that work toward it. A milestone none of whose purposes is registered,
or that needs an item with no recipe yet, is skipped: it counts for nothing and the day plan
leaves it out. So goals name purposes by name, and grow as other modules register those purposes.
A goal's progress is the mean of its counted milestones' shares; it is complete when every one is
whole. A goal is reached once in a life, unless it repeats (`repeat`: a discovery goal, measured
from when it was set, is on offer again once reached).

Modules register goals on import (backend.survival.life_goals registers the ones Mimo has).

The brain keeps its goal in state["brain"]:
- goal: {"name", "since", "picker", "progress", "best", "best_at", "plan", "plan_day",
  "checked_at", "day_start"} or None. `plan` is the day plan, [{"text", "done", "step"}]: the next
  milestones toward the goal (step is the milestone's index), written at dawn and when a goal is
  chosen. `day_start` is when the current game day began (set at dawn): `idle` measures no-progress
  time from there, not from midnight-crossing best_at, so only daylight counts.
- goal_due: a goal choice Mimo waits for, {"id", "reasons", "since"}, or None (ids come from
  the brain's next_id, like pending purpose choices).
- goal_penalties: {goal: server time until which it is not offered, after it was given up}.
- goal_idle_at: when a goal choice last found no goal open.
The goals Mimo reached are remembered in its world (memory_knowledge, fact "goal").

The tick tends the goal (`tend_goal`, from brain.notice_step). At most once a game minute it
reads the goal's progress: a complete goal is reached (a notable "goal" event, the goal's mood
reward, and a new goal and a new purpose are asked for); a goal no longer open is given up, and so
is one whose progress has not risen for IDLE game seconds of daylight while nothing that advances
it is on offer (`workable`). At dawn it writes the day plan (a routine "plan" event) and asks for a
goal choice: Jev may keep the goal or pick another, the rules picker keeps it. A goal whose
progress has not risen for a game day is given up at dawn instead. A goal given up is not offered
again for a game day. With no goal, a goal choice is asked for at once, then every IDLE_RETRY game
seconds while none is open. The worker's Chooser answers goal choices (backend.survival.choosing).

Purposes follow the goal (`toward`, used by pickers.steer): the purposes on offer that advance
the goal score GOAL_BOOST more (`boosted`: not past GOAL_TOP, and not late in the day or at
night, so going home and sleep still come first). While anything advances the goal or meets a
need (a purpose in NEEDS, or one whose urge Mimo feels now, `URGES`, scoring NEED_FLOOR or more),
only those are offered: the others, rest and explore among them, would be capped in the leisure
band anyway, and leaving them out keeps a model's pick on the goal too. When nothing for the goal is on offer now (torches wait for the
evening, a hunt for hides for its gap), the best other open goal that has something on offer is
worked toward meanwhile. A purpose whose work depends on why it is done says for itself whether it
advances a goal right now (`ADVANCES`: an explore trip does when its reason serves the goal,
backend.survival.scouting); any other purpose a milestone still to do names advances its goal.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Callable

from backend.services.crafting import RECIPES
from backend.survival.clock import DAY_SECONDS
from backend.survival.memory import know, known
from backend.survival.once import log_once
from backend.survival.purposes import PURPOSES, SURVIVAL_FLOOR, is_valid, late_day
from backend.survival.situation import Situation, in_tick
from backend.survival.triggers import ensure_brain, mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

GOAL_BOOST = 15.0  # purposes that advance the goal score this much more...
GOAL_TOP = SURVIVAL_FLOOR  # ...but never into the survival band (80 and up): staying alive comes first
NEED_FLOOR = 50.0  # a purpose in NEEDS meets a need when it scores at least this
# The survival and needs bands of purposes.py, and M5's keeping of home and arms.
# L4a final fix wave, I3: farm too (it tends and harvests the crops Mimo eats).
NEEDS = frozenset({"sleep", "go_home", "eat", "cook", "forage", "fish", "hunt", "farm", "build_shelter", "light_up",
                   "build_storage", "drop_items"})
GOAL_MOOD = 15.0  # mood a reached goal gives, unless the goal says otherwise
CHECK_EVERY = 60.0  # game seconds between two readings of the goal's progress in the tick
STALL = DAY_SECONDS  # game seconds without progress after which a goal is given up at dawn
IDLE = DAY_SECONDS / 3  # by day, this long without progress and nothing on offer for it: given up
SET_ASIDE = DAY_SECONDS  # game seconds a goal given up is not offered again
IDLE_RETRY = 600.0  # game seconds between two goal choices while no goal is open
STICK = 100.0  # the rules picker keeps the current goal (a stalled one was given up before)...
WORKABLE = 20.0  # ...and otherwise prefers a goal something can be done for right now
OFFERED = 4  # goals offered at a choice, the current one among them
PLAN_STEPS = 3  # milestones on the day plan
NEXT_SHOWN = 2  # milestones named in a goal's facts
REACHED = "goal"  # the memory_knowledge fact for a goal Mimo reached


@dataclass(frozen=True)
class Milestone:
    text: str  # "Make an iron pickaxe"
    share: Callable[[Situation], float]  # how much of it is done, 0 to 1
    purposes: tuple[str, ...]  # the purposes that work toward it
    items: tuple[str, ...] = ()  # items it needs a recipe for (L3's): skipped while one has none


def always(s: Situation) -> bool:
    return True


@dataclass(frozen=True)
class Goal:
    name: str
    title: str  # "Iron tools"
    why: str  # one sentence for the model and the HUD
    milestones: tuple[Milestone, ...]
    score: Callable[[Situation], float]  # the rules picker's score
    thought: str  # what Mimo thinks when it sets out
    after: tuple[str, ...] = ()  # goals that must be settled first
    valid: Callable[[Situation], bool] = always
    reward: float = GOAL_MOOD
    repeat: bool = False  # on offer again once reached (its milestones count from when it was set)


GOALS: dict[str, Goal] = {}


def register_goal(goal: Goal) -> Goal:
    """Add a goal, or replace the one with the same name."""
    GOALS[goal.name] = goal
    return goal


def lower(text: str) -> str:
    return text[:1].lower() + text[1:]


# Progress --------------------------------------------------------------------------------------

def counted(goal: Goal) -> list[tuple[int, Milestone]]:
    """The goal's milestones that count, with their index: a purpose of theirs is registered and
    every item they need has a recipe."""
    return [(index, milestone) for index, milestone in enumerate(goal.milestones)
            if any(name in PURPOSES for name in milestone.purposes)
            and all(item in RECIPES for item in milestone.items)]


def share_of(s: Situation, milestone: Milestone) -> float:
    """A milestone's share, read once per Situation. One that crashes counts as 0 (logged once)."""
    def look() -> float:
        try:
            share = float(milestone.share(s))
        except Exception as error:
            log_once(logger, f"milestone {milestone.text!r}", error)
            return 0.0
        return min(1.0, max(0.0, share)) if math.isfinite(share) else 0.0
    return s.sensed(f"milestone {id(milestone)}", look)


def progress_of(s: Situation, goal: Goal) -> float:
    steps = counted(goal)
    return sum(share_of(s, milestone) for _, milestone in steps) / len(steps) if steps else 0.0


def complete(s: Situation, goal: Goal) -> bool:
    steps = counted(goal)
    return bool(steps) and all(share_of(s, milestone) >= 1.0 for _, milestone in steps)


def ahead(s: Situation, goal: Goal) -> list[tuple[int, Milestone]]:
    """The counted milestones still to do, in order."""
    return [(index, milestone) for index, milestone in counted(goal) if share_of(s, milestone) < 1.0]


def reached(s: Situation) -> tuple[str, ...]:
    """The goals Mimo reached in this life, first first."""
    return s.sensed("goals reached", lambda: tuple(known(s.db, REACHED)) if s.db is not None else ())


def settled(s: Situation, name: str) -> bool:
    goal = GOALS.get(name)
    return name in reached(s) or (goal is not None and complete(s, goal))


def is_open(s: Situation, goal: Goal) -> bool:
    """On offer: a milestone counts, the goals before it are settled, it is valid, not reached yet
    (unless it repeats) and not complete. A validity check that crashes counts as not valid (logged
    once)."""
    if not counted(goal) or (goal.name in reached(s) and not goal.repeat):
        return False
    if not all(settled(s, name) for name in goal.after):
        return False
    try:
        valid = bool(goal.valid(s))
    except Exception as error:
        log_once(logger, f"goal {goal.name} validity", error)
        return False
    return valid and not complete(s, goal)


# The brain's goal ------------------------------------------------------------------------------

def goal_state(state: dict) -> dict:
    """The brain, with the goal fields a world from before L4 lacks."""
    brain = ensure_brain(state)
    brain.setdefault("goal", None)
    brain.setdefault("goal_due", None)
    brain.setdefault("goal_penalties", {})
    brain.setdefault("goal_idle_at", None)
    return brain


def active(s: Situation) -> Goal | None:
    """The goal Mimo works toward now, or None."""
    goal = s.brain.get("goal")
    return GOALS.get(goal["name"]) if goal else None


def ask_for_goal(state: dict, reason: str, at: float, fresh: bool = False) -> None:
    """Ask for a goal choice. A pending one keeps its id and gains the reason, unless `fresh`: then
    it gets a new id instead (as mark_trigger(fresh=True) does for purpose choices), so an answer
    still being worked out for the old id is thrown away when it arrives: the goal moved on."""
    brain = goal_state(state)
    due = brain["goal_due"]
    if due is not None and not fresh:
        if reason not in due["reasons"]:
            due["reasons"] = [*due["reasons"], reason]
        return
    reasons = [] if due is None else [known for known in due["reasons"] if known != reason]
    brain["goal_due"] = {"id": brain["next_id"], "reasons": [*reasons, reason],
                         "since": at if due is None else due["since"]}
    brain["next_id"] += 1


def adopt_goal(state: dict, name: str | None, picker: str, thought: str, at: float) -> bool:
    """Answer the goal choice with `name` (None: no goal is open). True for a new goal: it starts
    from nothing, the next tick writes its day plan, and the purpose is chosen again under it."""
    brain = goal_state(state)
    brain["goal_due"] = None
    current = brain["goal"]
    if name is None or name not in GOALS:
        brain["goal_idle_at"] = at
        return False
    if current is not None and current["name"] == name:
        current["picker"] = picker
        return False
    brain["goal"] = {"name": name, "since": at, "picker": picker, "progress": 0.0, "best": -1.0, "best_at": at,
                     "plan": None, "plan_day": None, "checked_at": None, "day_start": at}
    state["last_thought"] = thought
    mark_trigger(state, "goal", at, fresh=True)  # a purpose answer in flight no longer fits
    return True


# Purposes follow the goal ----------------------------------------------------------------------

# {purpose: check(s, goal)} for purposes that advance a goal only as they would be done now.
ADVANCES: dict[str, Callable[[Situation, Goal], bool]] = {}


def advances(s: Situation, name: str, goal: Goal) -> bool:
    """The purpose, named by a milestone of the goal still to do, would advance it now: always,
    unless it has a check of its own (ADVANCES). A check that crashes counts as no (logged once)."""
    check = ADVANCES.get(name)
    if check is None:
        return True
    try:
        return bool(check(s, goal))
    except Exception as error:
        log_once(logger, f"{name} advances {goal.name}", error)
        return False


def advancing(s: Situation, goal: Goal) -> frozenset[str]:
    """The registered purposes that would advance the goal now (the milestones still to do name them)."""
    return frozenset(name for _, milestone in ahead(s, goal) for name in milestone.purposes
                     if name in PURPOSES and advances(s, name, goal))


def goal_purposes(s: Situation) -> frozenset[str] | None:
    """The purposes that advance the goal now, or None without a goal."""
    goal = active(s)
    if goal is None:
        return None
    return s.sensed("goal purposes", lambda: advancing(s, goal))


def penalized(s: Situation, name: str) -> bool:
    return s.brain.get("goal_penalties", {}).get(name, -math.inf) > s.at


def own_score(s: Situation, goal: Goal) -> float | None:
    try:
        return float(goal.score(s))
    except Exception as error:
        log_once(logger, f"goal {goal.name} score", error)
        return None


def toward(s: Situation, offered_now: set[str]) -> tuple[Goal, frozenset[str]] | None:
    """The goal the options on offer work toward, with those that advance it: Mimo's goal when
    something for it is on offer; else the best other open goal (by its own score) that has
    something on offer, worked toward meanwhile. None without a goal, or with nothing on offer
    for any open goal."""
    current = active(s)
    if current is None:
        return None
    names = (goal_purposes(s) or frozenset()) & offered_now
    if names:
        return current, names
    best: tuple[float, Goal, frozenset[str]] | None = None
    for name in sorted(GOALS):
        goal = GOALS[name]
        if goal.name == current.name or penalized(s, goal.name) or not is_open(s, goal):
            continue
        names = advancing(s, goal) & offered_now
        score = own_score(s, goal) if names else None
        if score is not None and (best is None or score > best[0]):
            best = (score, goal, names)
    return (best[1], best[2]) if best else None


def boosted(s: Situation, score: float) -> float:
    """The score of a purpose that advances a goal: GOAL_BOOST more, not past GOAL_TOP and never
    lower. Late in the day and at night the goal waits for tomorrow: no boost."""
    if s.night or late_day(s):
        return score
    return max(score, min(score + GOAL_BOOST, GOAL_TOP))


# {purpose: urge(s)}: a purpose that meets a need while Mimo feels its urge (L4's curiosity: explore,
# once restless; the final fix wave's food trip: explore, when its best reason is food). Add one with
# add_urge, so two modules' urges for the same purpose both count.
URGES: dict[str, Callable[[Situation], bool]] = {}


def felt(name: str, urge: Callable[[Situation], bool], s: Situation) -> bool:
    """Whether Mimo feels the urge now. One that crashes counts as not felt (logged once)."""
    try:
        return bool(urge(s))
    except Exception as error:
        log_once(logger, f"{name} urge", error)
        return False


def add_urge(name: str, urge: Callable[[Situation], bool]) -> None:
    """Add an urge for the purpose `name`: with one there already, either one felt is enough."""
    before = URGES.get(name)
    URGES[name] = urge if before is None else (lambda s: felt(name, before, s) or felt(name, urge, s))


def meets_need(s: Situation, name: str, score: float) -> bool:
    """The purpose meets a need: a survival or needs purpose, or one whose urge Mimo feels now, scoring
    NEED_FLOOR or more. An urge that crashes counts as not felt (logged once)."""
    if score < NEED_FLOOR:
        return False
    if name in NEEDS:
        return True
    urge = URGES.get(name)
    return urge is not None and felt(name, urge, s)


# The goal in the tick --------------------------------------------------------------------------

def stalled(s: Situation) -> bool:
    """The goal's progress has not risen for STALL game seconds."""
    goal = s.brain.get("goal")
    return goal is not None and (s.at - goal["best_at"]) * s.scale >= STALL


def as_goal(s: Situation, goal: Goal) -> Situation:
    """`s` as if `goal` were Mimo's goal, on a copy of the state: some purposes are offered only for
    a goal of their own (improve_home, stock_larder, a hunt for hides)."""
    current = s.brain.get("goal")
    if current is not None and current["name"] == goal.name:
        return s
    fake = {"name": goal.name, "since": s.at, "best_at": s.at, "best": -1.0, "plan": None}
    return replace(s, state={**s.state, "brain": {**s.brain, "goal": fake}}, memo={})


def workable(s: Situation, goal: Goal) -> bool:
    """Something that advances the goal would be on offer now, were it Mimo's goal."""
    t = as_goal(s, goal)
    return any(is_valid(PURPOSES[name], t) for name in advancing(t, goal))


def idle(s: Situation, goal: Goal) -> bool:
    """By day, the goal's progress has not risen for IDLE game seconds of daylight and nothing that
    advances it is on offer: there is nothing to do for it. Measured from best_at or the start of
    today, whichever is later, so a night spent asleep (or several) is never counted against it."""
    current = s.brain["goal"]
    since = max(current["best_at"], current.get("day_start", current["best_at"]))
    return (not s.night and not late_day(s) and (s.at - since) * s.scale >= IDLE and not workable(s, goal))


# Functions of (Situation, Goal) giving a step the day plan also sets time aside for, or None (L4's
# curiosity adds time to wander once needs are met). Such a step has no milestone ("step": None).
PLAN_EXTRAS: list = []


def day_plan(s: Situation, goal: Goal) -> list[dict]:
    """The next PLAN_STEPS milestones toward the goal, then whatever else the day sets time aside for
    (PLAN_EXTRAS: one that crashes, or gives anything but None or a JSON-safe dict with a string
    "text", is left out, logged once, and never stalls the plan)."""
    plan = [{"text": milestone.text, "done": False, "step": index} for index, milestone in ahead(s, goal)[:PLAN_STEPS]]
    for extra in PLAN_EXTRAS:
        try:
            entry = extra(s, goal)
            if entry is None:
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
                raise ValueError(f"not a dict with a text: {entry!r}")
            json.dumps(entry)  # JSON-safe values only: this rides in the model payload and the HUD
        except Exception as error:
            log_once(logger, "day plan extra", error)
            continue
        plan.append({"done": False, "step": None, **entry})
    return plan


def plan_sentence(name: str, plan: list[dict]) -> str:
    words = [lower(entry["text"]) for entry in plan]
    listed = words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"
    return f"{name}'s plan for today: {listed}."


def reach_goal(state: dict, context: ActionContext, goal: Goal, at: float) -> None:
    """A notable "goal" event, the goal's mood reward, the goal remembered, and new choices. A
    non-repeating goal already known as reached (a stale answer re-adopted it and it completed
    again) gets neither: only its first reach is a celebration."""
    goal_state(state)["goal"] = None
    first = know(context.db, goal.name, REACHED, at)
    if first or goal.repeat:
        context.events.append((at, "goal", f"{state['name']} reached a goal: {lower(goal.title)}."))
        state["vitals"]["mood"] = min(100.0, state["vitals"]["mood"] + goal.reward)
        state["last_thought"] = f"I did it: {lower(goal.title)}!"
    ask_for_goal(state, "reached", at, fresh=True)
    mark_trigger(state, "goal", at, fresh=True)  # a purpose answer in flight no longer fits


def give_up_goal(state: dict, context: ActionContext, name: str, at: float, why: str, scale: float) -> None:
    """A routine "plan" event, the goal set aside for SET_ASIDE game seconds, and new choices."""
    brain = goal_state(state)
    brain["goal"] = None
    brain["goal_penalties"][name] = at + SET_ASIDE / scale
    title = lower(GOALS[name].title) if name in GOALS else name.replace("_", " ")
    context.events.append((at, "plan", f"{state['name']} set a goal aside for now: {title} ({why})."))
    ask_for_goal(state, "given_up", at, fresh=True)
    mark_trigger(state, "goal", at, fresh=True)  # a purpose answer in flight no longer fits


def check_goal(state: dict, context: ActionContext, at: float, dawn: bool) -> None:
    brain = goal_state(state)
    current = brain["goal"]
    s = in_tick(state, context, at)
    goal = GOALS.get(current["name"])
    if goal is None or not counted(goal):
        give_up_goal(state, context, current["name"], at, "it is not known any more", s.scale)
        return
    current["checked_at"] = at
    if dawn:
        current["day_start"] = at
    if complete(s, goal):
        reach_goal(state, context, goal, at)
        return
    if not is_open(s, goal):
        give_up_goal(state, context, goal.name, at, "it cannot be done now", s.scale)
        return
    progress = progress_of(s, goal)
    current["progress"] = round(progress, 3)
    if progress > current["best"] + 1e-6:
        current.update(best=progress, best_at=at)
    if dawn and stalled(s):
        give_up_goal(state, context, goal.name, at, "no progress for a day", s.scale)
        return
    if not dawn and idle(s, goal):
        give_up_goal(state, context, goal.name, at, "nothing to do for it now", s.scale)
        return
    if dawn or current["plan"] is None:
        current["plan"] = day_plan(s, goal)
        current["plan_day"] = s.clock["day_number"]
        if current["plan"]:
            context.events.append((at, "plan", plan_sentence(state["name"], current["plan"])))
    else:
        for entry in current["plan"]:
            step = entry.get("step")
            if isinstance(step, int) and 0 <= step < len(goal.milestones):
                entry["done"] = share_of(s, goal.milestones[step]) >= 1.0
    if dawn:
        ask_for_goal(state, "dawn", at)


def tend_goal(state: dict, context: ActionContext, at: float, phase: str | None) -> None:
    """The goal after a vitals step (brain.notice_step): see the module docstring. A crash is
    logged once and the tick goes on."""
    if context.db is None or state.get("died_at") is not None:
        return
    try:
        brain = goal_state(state)
        scale = context.clock_at(at)["time_scale"]
        dawn = phase == "dawn"
        current = brain["goal"]
        if current is None:
            idle_at = brain["goal_idle_at"]
            if brain["goal_due"] is None and (dawn or idle_at is None or (at - idle_at) * scale >= IDLE_RETRY):
                ask_for_goal(state, "dawn" if dawn else "no_goal", at)
            return
        checked = current.get("checked_at")
        if dawn or current["plan"] is None or checked is None or (at - checked) * scale >= CHECK_EVERY:
            check_goal(state, context, at, dawn)
    except Exception as error:
        log_once(logger, "goals", error)


# Offering goals --------------------------------------------------------------------------------

def goal_facts(s: Situation, goal: Goal) -> str:
    """Progress and the next milestones in words: "40% done; next: find iron ore, mine 3 iron ore"."""
    words = [lower(milestone.text) for _, milestone in ahead(s, goal)[:NEXT_SHOWN]]
    current = active(s)
    mine = " (its goal now)" if current is not None and current.name == goal.name else ""
    later = "" if workable(s, goal) else "; nothing to do for it right now"
    return f"{round(progress_of(s, goal) * 100)}% done{mine}; next: {', '.join(words) or 'nothing'}{later}"


def rules_score(s: Situation, goal: Goal) -> float:
    """The goal's own score, WORKABLE more when something can be done for it now, and STICK more
    for the current goal unless it stalled: the rules keep a goal for as long as it moves."""
    score = own_score(s, goal)
    if score is None:
        return 0.0
    if workable(s, goal):
        score += WORKABLE
    current = active(s)
    if current is not None and current.name == goal.name and not stalled(s):
        score += STICK
    return score


def offers(s: Situation) -> list[tuple[Goal, str, float]]:
    """The goals on offer as (goal, facts, rules score), best first: the current one while it is
    open, the best goal that repeats (L4's discovery goals are always on offer), and the best
    others, OFFERED in all. Goals given up lately are left out."""
    found = [(goal, goal_facts(s, goal), rules_score(s, goal)) for _, goal in sorted(GOALS.items())
             if is_open(s, goal) and not penalized(s, goal.name)]
    found.sort(key=lambda entry: -entry[2])
    current = active(s)
    kept = [entry for entry in found if current is not None and entry[0].name == current.name]
    if not any(entry[0].repeat for entry in kept):
        kept += [entry for entry in found if entry[0].repeat][:1]
    others = [entry for entry in found if entry not in kept]
    return sorted(kept + others[:OFFERED - len(kept)], key=lambda entry: -entry[2])


def reached_titles(s: Situation) -> list[str]:
    return [GOALS[name].title if name in GOALS else name.replace("_", " ") for name in reached(s)]


# What the model and the viewer are told ---------------------------------------------------------

def goal_payload(s: Situation) -> dict | None:
    """The goal for the model: its title, why, progress, next milestones and days on it; or None."""
    goal = active(s)
    if goal is None:
        return None
    since = s.brain["goal"]["since"]
    return {"title": goal.title, "why": goal.why, "progress": round(progress_of(s, goal), 2),
            "next_steps": [milestone.text for _, milestone in ahead(s, goal)[:PLAN_STEPS]],
            "days_on_it": math.floor(max(0.0, s.at - since) * s.scale / DAY_SECONDS)}


def goal_view(brain: dict | None) -> dict | None:
    """The goal for /api/mimo: name, title, why, progress (0 to 1), the day plan, who chose it and
    when; None without one."""
    current = (brain or {}).get("goal")
    if not current:
        return None
    goal = GOALS.get(current["name"])
    return {"name": current["name"], "title": goal.title if goal else current["name"].replace("_", " "),
            "why": goal.why if goal else "", "progress": round(float(current.get("progress") or 0.0), 2),
            "plan": [{"text": entry["text"], "done": bool(entry.get("done"))} for entry in current.get("plan") or []],
            "picker": current.get("picker"), "since": current.get("since")}


def reached_rows(db: sqlite3.Connection) -> list[tuple[str, float]]:
    """(goal, when) for every goal reached, first first. A world from before M3 reached none."""
    try:
        rows = db.execute("SELECT subject, learned_at FROM memory_knowledge WHERE fact=? ORDER BY learned_at, subject",
                          (REACHED,)).fetchall()
    except sqlite3.OperationalError as error:
        if "no such table" not in str(error):
            raise
        return []
    return [(row[0], row[1]) for row in rows]
