"""Choosing a purpose in the worker, outside the world's write transaction.

After each tick the worker calls `Chooser.poll`. When the active life has a pending trigger:

1. `prepare` reads a snapshot on a read-only connection: the purposes on offer with facts and
   scores, the model payload, and which picker may answer (the route): Jev when TYPESAFE_API_KEY
   is set, else Luna when MIMO_MODEL_API_KEY or OPENAI_API_KEY is set, else utility. Utility also
   answers
   - when a daily cap is spent (MIMO_MAX_DECISIONS_PER_DAY, default 2000, counts Jev and Luna
     picks; MIMO_MAX_LUNA_DECISIONS_PER_DAY every Luna call);
   - when Jev's or Luna's own rolling budget for the game hour before now (3,600 game seconds on
     the life's clock, so it holds at any MIMO_TIME_SCALE) is spent: MIMO_JEV_CALLS_PER_HOUR
     (default 60; Jev is cheap) or MIMO_LUNA_CALLS_PER_HOUR (default 8; Luna is not), even for a
     vital crossing;
   - when a short purpose (rest, explore, eat, go_home) just ended in the ordinary way
     (plan_done, idle or reflex_ended) and nothing more significant (dawn, dusk, a discovery, a
     hello, a failed plan, a quiet game hour, a vital crossing) is waiting;
   - when the last model call was less than 60 real seconds ago and no vital crossing is waiting.
   A dawn, hello or discovery choice made by a model also gets a Luna reflection as its thought,
   at most 12 per UTC day.
2. A utility answer is decided and stored at once. A model answer is decided in one background
   thread while the worker keeps ticking; `decide` never raises: a failed call or an answer that
   was not offered falls back to utility, and the error is logged once. A call still unanswered
   15 s after its timeouts (urllib's timeout does not cover a DNS lookup or a trickling answer)
   is given up: the stuck thread is left behind with its executor, a fresh one takes new work,
   the call is counted and the utility picker answers the same ask.
3. `store_choice` saves the answer in a short transaction, unless the life died, nothing is
   pending any more or the pending id changed (the state moved on). Model calls count either way.
   A `purpose` event is logged only when the purpose differs from the one chosen last, or when a
   model's pick brings a new thought, so re-choosing rest after rest stays out of the event log.

While a choice is pending, the brain keeps Mimo on its current plan, or waiting.

L4: goals. When the tick asks for a goal (backend.survival.goals: with none, at dawn, or when one
was reached or given up), `poll` answers that first — unless the pending purpose choice is urgent
(a vital crossing), which goes first instead, so a goal call on Jev, in the background for up to
35 s, never delays it. `prepare_goal` offers the open goals with their facts and rules scores
(goals.offers) and why Jev is asked now (`goal_trigger`, from goal_due's own reasons, not the
purpose's). Jev chooses when it is configured, more than one goal is on offer and neither the daily
cap nor its hourly budget is spent; a goal call counts toward both, but it does not start the
60-second gap before the next model call, so the purpose choice that follows a goal may still go to
Jev. Otherwise the rules picker takes the best score (the current goal keeps its lead). Luna never
chooses goals. A rules answer is stored at once and the purpose choice follows in the same poll;
`store_goal` saves a goal unless the ask went stale or the goal it names has since been set aside or
closed (reach_goal and give_up_goal give a pending ask a fresh id, so an answer still in flight when
the goal ends is thrown away), and a new goal asks for the purpose again (goals.adopt_goal). With a
goal, a purpose that ended in the ordinary way is chosen again by the rules picker (`routine`): Jev
speaks at the moments that matter (dawn, dusk, discoveries, new goals, vital crossings and the
like), and the goal carries the day between them. A purpose that works toward a goal says so in its
event: Mimo's own goal, or, meanwhile (resolution 8), the best other open goal with something on
offer (goals.toward, pickers.steer). `store_choice` keeps that aim as long as the named goal is
still one Mimo would work toward — registered, open and not penalized — and drops it only once the
goal itself has ended; the fresh purpose id above already discards a choice whose own goal ended
while it was in flight, so this is a backstop, not the main defense.

L4: explore always goes for a reason (backend.survival.trips). Its option carries the reasons on
offer, the rules' pick first, and choosing explore goes for that one: the trip is stored in the
brain, and its event and thought say what for ("Pip decided to explore to look for iron, toward
iron tools. \"Heading north to look for iron. My pickaxe needs it.\"").
"""

from __future__ import annotations

import logging
import os
import random
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from backend.survival.actions import ensure_actions, kept_steps, record
from backend.survival.care import utc_day
from backend.survival.clock import time_scale
from backend.survival.goals import GOALS, active, adopt_goal, goal_state, is_open, lower, offers, penalized, reached_titles
from backend.survival.models import (
    GOAL_INSTRUCTIONS, JEV_TIMEOUT, LUNA_TIMEOUT, Http, ModelError, ask_jev, ask_luna, jev_configured,
    luna_configured, luna_reflect, post_json,
)
from backend.survival.once import log_once
from backend.survival.pickers import Option, context_payload, options, thought_for, utility_pick
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.triggers import HOUR, ensure_brain
from backend.survival.trips import Offer, start_trip, trip_thought
from backend.survival.world import SurvivalWorld, log_event, read_state, recent_events, write_state

logger = logging.getLogger(__name__)

MODEL_GAP = 60.0
GIVE_UP_AFTER = 15.0  # seconds past a model call's own timeouts
REFLECTION_CAP = 12
REFLECT_ON = ("dawn", "hello", "discovery")
DECISION_CAP = ("MIMO_MAX_DECISIONS_PER_DAY", 2000)
# A short purpose that ends for one of these reasons alone is chosen again by the utility picker.
SHORT_PURPOSES = frozenset({"rest", "explore", "eat", "go_home"})
ROUTINE_REASONS = frozenset({"plan_done", "idle", "reflex_ended"})
LUNA_CAP = ("MIMO_MAX_LUNA_DECISIONS_PER_DAY", 64)
# Rolling game-hour budgets, one per picker: Jev is cheap, so it gets a much bigger allowance.
JEV_HOUR_CAP = ("MIMO_JEV_CALLS_PER_HOUR", 60)
LUNA_HOUR_CAP = ("MIMO_LUNA_CALLS_PER_HOUR", 8)
EVENTS_SHOWN = 8

Env = Mapping[str, str]


@dataclass(frozen=True)
class Ask:
    pending_id: int
    route: str  # "jev", "luna" or "utility"
    reflect: bool
    options: tuple[Option, ...]
    payload: dict
    asked_at: float
    game_at: float = 0.0  # game seconds since the life began, when asked
    kind: str = "purpose"  # L4: or "goal"


@dataclass(frozen=True)
class Choice:
    purpose: str
    picker: str
    thought: str
    calls: dict  # {"model": n, "luna": n, "reflections": n}
    error: str | None = None
    trip: Offer | None = None  # L4: explore's reason (trips.Offer)


def cap(env: Env, setting: tuple[str, int]) -> int:
    name, default = setting
    try:
        return max(0, int(env.get(name, default)))
    except (TypeError, ValueError):
        return default


def calls_today(brain: dict, now: float) -> dict:
    """Today's model-call counters, starting over on a new UTC day."""
    today = utc_day(now)
    if brain["calls"].get("day") != today:
        brain["calls"] = {"day": today, "model": 0, "luna": 0, "reflections": 0}
    return brain["calls"]


def recent_calls(brain: dict, key: str, game_at: float) -> list[float]:
    """The game times of the picks in `brain[key]` (one picker's own list) made in the game hour
    before `game_at`."""
    return [at for at in brain.get(key, []) if game_at - HOUR < at <= game_at]


def routine(brain: dict, steady: bool = False) -> bool:
    """A short purpose ended in the ordinary way, with nothing more significant waiting. L4: with a
    goal (`steady`), any purpose that ended in the ordinary way: the rules picker carries the goal on
    between the moments that matter."""
    reasons = set(brain["pending"]["reasons"])
    short = steady or brain.get("last_chosen") in SHORT_PURPOSES
    return short and bool(reasons) and reasons <= ROUTINE_REASONS


def route_for(brain: dict, now: float, env: Env, game_at: float, steady: bool = False) -> str:
    """Who may answer the pending choice: "jev", "luna" or "utility". `game_at` is the life's game
    time in seconds, for each picker's own rolling game-hour budget (MIMO_JEV_CALLS_PER_HOUR,
    MIMO_LUNA_CALLS_PER_HOUR): once a picker's budget is spent it does not borrow the other's."""
    counters = calls_today(brain, now)
    if counters["model"] >= cap(env, DECISION_CAP) or routine(brain, steady):
        return "utility"
    if not brain["pending"]["urgent"] and brain["last_call_at"] is not None and now - brain["last_call_at"] < MODEL_GAP:
        return "utility"
    if jev_configured(env):
        if len(recent_calls(brain, "jev_calls", game_at)) >= cap(env, JEV_HOUR_CAP):
            return "utility"
        return "jev"
    if luna_configured(env):
        if counters["luna"] >= cap(env, LUNA_CAP) or len(recent_calls(brain, "luna_calls", game_at)) >= cap(
                env, LUNA_HOUR_CAP):
            return "utility"
        return "luna"
    return "utility"


def reflect_for(brain: dict, route: str, now: float, env: Env) -> bool:
    """Whether Luna adds a reflection to a model's choice: dawn, hello or discovery, within the caps."""
    if route == "utility" or not luna_configured(env):
        return False
    if not any(reason in REFLECT_ON for reason in brain["pending"]["reasons"]):
        return False
    counters = calls_today(brain, now)
    luna_after_pick = counters["luna"] + (1 if route == "luna" else 0)
    return counters["reflections"] < REFLECTION_CAP and luna_after_pick < cap(env, LUNA_CAP)


def urgent_pending(world: SurvivalWorld) -> bool:
    """Whether the pending purpose choice, if any, is urgent (a vital crossing): an urgent choice
    goes first in `Chooser.poll`, so a slow goal call on Jev never delays it by its own 35 s."""
    with world.connect() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return False
        pending = ensure_brain(state)["pending"]
    return bool(pending and pending["urgent"])


def prepare(world: SurvivalWorld, now: float, scale: float, env: Env) -> Ask | None:
    """A read-only snapshot of the pending choice, or None when nothing is pending."""
    with world.connect() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        ensure_actions(state)  # a world the worker has not ticked yet has no action fields
        brain = ensure_brain(state)
        if brain["pending"] is None:
            return None
        s = from_db(db, state, now, scale)
        choices = options(s)
        payload = context_payload(s, recent_events(db, EVENTS_SHOWN))
        steady = active(s) is not None
    if not choices:
        return None
    game_at = max(0.0, now - state["born_at"]) * scale
    route = route_for(brain, now, env, game_at, steady)
    return Ask(brain["pending"]["id"], route, reflect_for(brain, route, now, env), tuple(choices), payload, now,
               game_at)


def decide(ask: Ask, env: Env, http: Http, rng: random.Random) -> Choice:
    """Answer an Ask. Never raises: model failures fall back to the utility picker."""
    calls = {"model": 0, "luna": 0, "reflections": 0}
    choices, errors = list(ask.options), []
    purpose, picker = None, "utility"
    if ask.route in ("jev", "luna"):
        calls["model"] += 1
        if ask.route == "luna":
            calls["luna"] += 1
        try:
            if ask.kind == "goal":
                purpose = ask_jev(ask.payload, choices, env, http, question="goal", instructions=GOAL_INSTRUCTIONS)
            else:
                purpose = (ask_jev if ask.route == "jev" else ask_luna)(ask.payload, choices, env, http)
            picker = ask.route
        except Exception as error:
            errors.append(f"{ask.route}: {error}")
    if purpose is None:
        purpose = utility_pick(choices, rng)
    trip = trip_for(ask, purpose)
    thought = trip_thought(trip) if trip is not None else answer_thought(ask, purpose, rng)
    if ask.reflect and picker != "utility":
        calls["luna"] += 1
        calls["reflections"] += 1
        option = next(option for option in choices if option.name == purpose)
        try:
            thought = luna_reflect(ask.payload, option, env, http)
        except Exception as error:
            errors.append(f"reflection: {error}")
    return Choice(purpose, picker, thought, calls, "; ".join(errors) or None, trip)


def trip_for(ask: Ask, purpose: str) -> Offer | None:
    """L4: the reason an explore choice goes for: the rules' pick, the first offered."""
    option = next((option for option in ask.options if option.name == purpose), None)
    if ask.kind != "purpose" or purpose != "explore" or option is None or not option.reasons:
        return None
    return option.reasons[0]


def answer_thought(ask: Ask, name: str, rng: random.Random) -> str:
    """What Mimo thinks of the answer: the goal's thought (L4), or one of the purpose's."""
    if ask.kind == "goal":
        return GOALS[name].thought if name in GOALS else f"I want {name.replace('_', ' ')}."
    return thought_for(name, rng)


def deadline(ask: Ask) -> float:
    """Seconds after asking when an unanswered model call is given up: the pick's timeout (Jev
    20 s, Luna 45 s), plus Luna's for a reflection, plus 15 s."""
    seconds = JEV_TIMEOUT if ask.route == "jev" else LUNA_TIMEOUT
    return seconds + (LUNA_TIMEOUT if ask.reflect else 0.0) + GIVE_UP_AFTER


def apply_choice(state: dict, choice: Choice, now: float) -> None:
    """Make the choice the current purpose. A new purpose drops the old plan (or, during a reflex,
    the steps the reflex set aside) but its cleanup steps, which run first, and ends a wait, or a
    sleep Mimo took while it waited for a choice, so the next tick plans at once."""
    brain = ensure_brain(state)
    changed = choice.purpose != brain["purpose"]
    brain.update(pending=None, picker=choice.picker, chosen_at=now, last_chosen=choice.purpose)
    if changed:
        brain.update(purpose=choice.purpose, batches=0, replans=0, planned_at=None,
                     handled_failure=state.get("last_failure"))
        if brain["reflex"] is not None:
            brain["set_aside"] = kept_steps(brain["set_aside"])
        else:
            state["queue"] = kept_steps(state["queue"])
            action = state.get("action") or {}
            if action.get("kind") == "wait":
                state["action"] = None
            elif action.get("kind") == "sleep" and "purpose" not in action and choice.purpose != "sleep":
                record(state, action, now, "interrupted", "choice")
                state["action"] = None
    state["last_thought"] = choice.thought


def store_choice(world: SurvivalWorld, ask: Ask, choice: Choice, now: float, scale: float = 1.0) -> str | None:
    """Save the choice unless the life died or the state moved on. Returns the purpose stored."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        ensure_actions(state)
        brain = ensure_brain(state)
        counters = calls_today(brain, now)
        for key, count in choice.calls.items():
            counters[key] += count
        if choice.calls["model"] or choice.calls["luna"]:
            brain["last_call_at"] = ask.asked_at
        if choice.calls["model"]:
            key = "jev_calls" if ask.route == "jev" else "luna_calls"
            brain[key] = [*recent_calls(brain, key, ask.game_at), ask.game_at]
        pending = brain["pending"]
        fresh = pending is not None and pending["id"] == ask.pending_id
        if fresh:
            new_purpose = choice.purpose != brain.get("last_chosen")
            new_thought = choice.picker != "utility" and choice.thought != state.get("last_thought")
            trip = brain.get("trip") or {}
            new_reason = choice.trip is not None and trip.get("reason") != choice.trip.reason
            fresh_trip = new_reason or brain["purpose"] != choice.purpose or trip.get("done")
            apply_choice(state, choice, now)
            if choice.trip is not None and fresh_trip:
                start_trip(brain, choice.trip, now, choice.picker)
            if new_purpose or new_thought or new_reason:
                purpose = PURPOSES.get(choice.purpose)
                phrase = purpose.phrase if purpose else choice.purpose.replace("_", " ")
                if choice.trip is not None:  # L4: explore says what for
                    phrase = f"{phrase} to {choice.trip.words}"
                # L4: a purpose that works toward a goal says which: Mimo's own goal, or, meanwhile
                # (resolution 8), the best other open goal with something on offer (goals.toward,
                # pickers.steer). Backstop only: the fresh purpose id above already drops a choice
                # whose own goal ended while it was in flight (round 1). This keeps the aim as long
                # as the named goal is still one Mimo would work toward — registered, open and not
                # just penalized — and drops it only once that goal itself has ended.
                goal = next((option.goal for option in ask.options if option.name == choice.purpose), "")
                aim = ""
                if goal:
                    named = next((candidate for candidate in GOALS.values() if candidate.title == goal), None)
                    if named is not None:
                        s = from_db(db, state, now, scale)
                        if is_open(s, named) and not penalized(s, named.name):
                            aim = f", toward {lower(goal)}"
                log_event(db, now, "purpose", f'{state["name"]} decided to {phrase}{aim}. "{choice.thought}"')
        write_state(db, state)
        return choice.purpose if fresh else None


def goal_route(brain: dict, now: float, env: Env, game_at: float, offered: int) -> str:
    """Who chooses a goal (L4): Jev, when configured, more than one goal is on offer and neither the
    daily cap nor Jev's hourly budget is spent; else the rules picker ("utility")."""
    if offered < 2 or not jev_configured(env) or calls_today(brain, now)["model"] >= cap(env, DECISION_CAP):
        return "utility"
    if len(recent_calls(brain, "jev_calls", game_at)) >= cap(env, JEV_HOUR_CAP):
        return "utility"
    return "jev"


# {reason: word} for the goal payload's goal_trigger: why Jev is asked to choose a goal now, since
# context_payload's own "trigger" holds the purpose's reasons, not goal_due's.
GOAL_TRIGGER_WORDS = {"dawn": "dawn", "reached": "reached", "given_up": "set aside", "no_goal": "none open"}


def goal_trigger(reasons: list[str]) -> str:
    """The first of `reasons` (goal_due's) with a word in GOAL_TRIGGER_WORDS, or ""."""
    return next((GOAL_TRIGGER_WORDS[reason] for reason in reasons if reason in GOAL_TRIGGER_WORDS), "")


def prepare_goal(world: SurvivalWorld, now: float, scale: float, env: Env) -> Ask | None:
    """A read-only snapshot of the goal choice the tick asked for (L4), or None when none is due.
    With no goal open the ask is answered at once: no goal, and the tick asks again later."""
    with world.connect() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        ensure_actions(state)
        brain = goal_state(state)
        due = brain["goal_due"]
        if due is None:
            return None
        s = from_db(db, state, now, scale)
        found = offers(s)
        choices = tuple(Option(goal.name, goal.title, goal.why, facts, score) for goal, facts, score in found)
        payload = {**context_payload(s, recent_events(db, EVENTS_SHOWN)), "goals_reached": reached_titles(s),
                  "goal_trigger": goal_trigger(due["reasons"])}
    game_at = max(0.0, now - state["born_at"]) * scale
    ask = Ask(due["id"], goal_route(brain, now, env, game_at, len(choices)), False, choices, payload, now, game_at,
              kind="goal")
    if not choices:
        store_goal(SurvivalWorld(world.path), ask, Choice("", "utility", "", {"model": 0, "luna": 0, "reflections": 0}),
                   now, scale)
        return None
    return ask


def store_goal(world: SurvivalWorld, ask: Ask, choice: Choice, now: float, scale: float = 1.0) -> str | None:
    """Save a goal choice unless the life died, the ask went stale, or the goal it names has since
    been set aside or is no longer open (a stale answer thrown out this way is asked again: unlike a
    stale id, goal_due is left pending). Counts its model call either way. A new goal is logged as a
    routine "plan" event. Returns the goal stored."""
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return None
        ensure_actions(state)
        brain = goal_state(state)
        counters = calls_today(brain, now)
        for key, count in choice.calls.items():
            counters[key] += count
        if choice.calls["model"]:
            brain["jev_calls"] = [*recent_calls(brain, "jev_calls", ask.game_at), ask.game_at]
        due = brain["goal_due"]
        fresh = due is not None and due["id"] == ask.pending_id
        name = choice.purpose or None
        if fresh and name is not None:
            goal = GOALS.get(name)
            s = from_db(db, state, now, scale)
            if goal is None or penalized(s, name) or not is_open(s, goal):
                fresh = False
        if fresh and adopt_goal(state, name, choice.picker, choice.thought, now):
            title = lower(GOALS[name].title)
            log_event(db, now, "plan", f'{state["name"]} set a new goal: {title}. "{choice.thought}"')
        write_state(db, state)
        return name if fresh else None


class InlineExecutor:
    """Runs submitted work at once in the calling thread (tests use it instead of a thread)."""

    def submit(self, fn: Callable, *args) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as error:
            future.set_exception(error)
        return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False) -> None:
        return None


def new_thread() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="mimo-chooser")


class Chooser:
    """Answers the active life's pending choices, one model call at a time in a background thread.

    `executor_factory` makes the executor that replaces one stuck on a hung call (tests pass one;
    the default is a new single-thread pool)."""

    def __init__(self, env: Env | None = None, http: Http = post_json, executor=None,
                 rng: random.Random | None = None, scale: float | None = None,
                 executor_factory: Callable[[], object] | None = None):
        self.env = os.environ if env is None else env
        self.http = http
        self.new_executor = executor_factory or new_thread
        self.executor = executor or self.new_executor()
        self.rng = rng or random.Random()
        self.scale = scale
        self.future: Future | None = None
        self.asked: tuple[Path, Ask] | None = None

    def poll(self, registry: LifeRegistry, now: float | None = None) -> str | None:
        """Store a finished answer, or start answering a new pending choice: a goal choice first
        (its rules answer settled at once, so the purpose choice can follow in the same poll), then
        the purpose. Returns the name stored: a purpose, or (a goal answered) the goal's name. An
        urgent purpose choice (a vital crossing) goes first instead: a slow goal call on Jev, in the
        background for up to 35 s, must never hold it up."""
        now = time.time() if now is None else now
        if self.future is not None:
            return self.collect(now)
        life = registry.active_life()
        if life is None:
            return None
        path = registry.world_path(life)
        scale = time_scale() if self.scale is None else self.scale
        world = SurvivalWorld(path, read_only=True)
        ask = None if urgent_pending(world) else prepare_goal(world, now, scale, self.env)
        if ask is not None and ask.route == "utility":
            self.store(path, ask, decide(ask, self.env, self.http, self.rng), now)
            ask = None
        ask = ask or prepare(world, now, scale, self.env)
        if ask is None:
            return None
        if ask.route == "utility":
            return self.store(path, ask, decide(ask, self.env, self.http, self.rng), now)
        self.asked = (path, ask)
        self.future = self.executor.submit(decide, ask, self.env, self.http, self.rng)
        return self.collect(now)

    def collect(self, now: float) -> str | None:
        if self.future is None or self.asked is None:
            return None
        (path, ask), future = self.asked, self.future
        if not future.done():
            return self.give_up(now) if now - ask.asked_at > deadline(ask) else None
        self.future, self.asked = None, None
        return self.store(path, ask, future.result(), now)

    def give_up(self, now: float) -> str | None:
        """Leave a hung call behind: new work goes to a fresh executor, the call is counted and
        the utility picker answers the same ask (store_choice still drops it if it went stale)."""
        (path, ask), future = self.asked, self.future
        self.future, self.asked = None, None
        future.cancel()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.executor = self.new_executor()
        purpose = utility_pick(list(ask.options), self.rng)
        calls = {"model": 1, "luna": 1 if ask.route == "luna" else 0, "reflections": 0}
        error = f"{ask.route}: no answer after {deadline(ask):g} s, gave up"
        # Fix round 1: a hung call that falls back to explore said what for in its event ("to look
        # for iron") but never in the thought, since it went through answer_thought alone.
        trip = trip_for(ask, purpose)
        thought = trip_thought(trip) if trip is not None else answer_thought(ask, purpose, self.rng)
        return self.store(path, ask, Choice(purpose, "utility", thought, calls, error, trip), now)

    def store(self, path: Path, ask: Ask, choice: Choice, now: float) -> str | None:
        if choice.error:
            log_once(logger, "picker", ModelError(choice.error))
        scale = time_scale() if self.scale is None else self.scale
        if ask.kind == "goal":
            return store_goal(SurvivalWorld(path), ask, choice, now, scale)
        return store_choice(SurvivalWorld(path), ask, choice, now, scale)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
