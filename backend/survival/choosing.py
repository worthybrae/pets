"""Choosing a purpose in the worker, outside the world's write transaction.

After each tick the worker calls `Chooser.poll`. When the active life has a pending trigger:

1. `prepare` reads a snapshot on a read-only connection: the purposes on offer with facts and
   scores, the model payload, and which picker may answer (the route): Jev when TYPESAFE_API_KEY
   is set, else Luna when MIMO_MODEL_API_KEY or OPENAI_API_KEY is set, else utility. Utility also
   answers
   - when a daily cap is spent (MIMO_MAX_DECISIONS_PER_DAY, default 200, counts Jev and Luna
     picks; MIMO_MAX_LUNA_DECISIONS_PER_DAY every Luna call);
   - when 8 model picks were made in the last game hour (3,600 game seconds on the life's clock,
     so the budget holds at any MIMO_TIME_SCALE), even for a vital crossing (spec section 11:
     3 to 8 calls per game hour);
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

While a choice is pending, the brain keeps Mimo on its current plan, or waiting.
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

from backend.survival.actions import ensure_actions, record
from backend.survival.care import utc_day
from backend.survival.clock import time_scale
from backend.survival.models import (
    JEV_TIMEOUT, LUNA_TIMEOUT, Http, ModelError, ask_jev, ask_luna, jev_configured, luna_configured,
    luna_reflect, post_json,
)
from backend.survival.once import log_once
from backend.survival.pickers import Option, context_payload, options, thought_for, utility_pick
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.situation import from_db
from backend.survival.triggers import HOUR, ensure_brain
from backend.survival.world import SurvivalWorld, log_event, read_state, write_state

logger = logging.getLogger(__name__)

MODEL_GAP = 60.0
GIVE_UP_AFTER = 15.0  # seconds past a model call's own timeouts
MODEL_BUDGET = 8  # model picks per rolling game hour
REFLECTION_CAP = 12
REFLECT_ON = ("dawn", "hello", "discovery")
DECISION_CAP = ("MIMO_MAX_DECISIONS_PER_DAY", 200)
# A short purpose that ends for one of these reasons alone is chosen again by the utility picker.
SHORT_PURPOSES = frozenset({"rest", "explore", "eat", "go_home"})
ROUTINE_REASONS = frozenset({"plan_done", "idle", "reflex_ended"})
LUNA_CAP = ("MIMO_MAX_LUNA_DECISIONS_PER_DAY", 64)
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


@dataclass(frozen=True)
class Choice:
    purpose: str
    picker: str
    thought: str
    calls: dict  # {"model": n, "luna": n, "reflections": n}
    error: str | None = None


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


def recent_model_calls(brain: dict, game_at: float) -> list[float]:
    """The game times of the model picks made in the game hour before `game_at`."""
    return [at for at in brain.get("model_calls", []) if game_at - HOUR < at <= game_at]


def routine(brain: dict) -> bool:
    """A short purpose ended in the ordinary way, with nothing more significant waiting."""
    reasons = set(brain["pending"]["reasons"])
    return brain.get("last_chosen") in SHORT_PURPOSES and bool(reasons) and reasons <= ROUTINE_REASONS


def route_for(brain: dict, now: float, env: Env, game_at: float) -> str:
    """Who may answer the pending choice: "jev", "luna" or "utility". `game_at` is the life's
    game time in seconds, for the budget of 8 model picks per game hour."""
    counters = calls_today(brain, now)
    if counters["model"] >= cap(env, DECISION_CAP):
        return "utility"
    if len(recent_model_calls(brain, game_at)) >= MODEL_BUDGET or routine(brain):
        return "utility"
    if not brain["pending"]["urgent"] and brain["last_call_at"] is not None and now - brain["last_call_at"] < MODEL_GAP:
        return "utility"
    if jev_configured(env):
        return "jev"
    if luna_configured(env) and counters["luna"] < cap(env, LUNA_CAP):
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
        events = [{"text": row[0]} for row in
                  db.execute("SELECT text FROM mimo_events ORDER BY id DESC LIMIT ?", (EVENTS_SHOWN,)).fetchall()]
        payload = context_payload(s, events)
    if not choices:
        return None
    game_at = max(0.0, now - state["born_at"]) * scale
    route = route_for(brain, now, env, game_at)
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
            purpose = (ask_jev if ask.route == "jev" else ask_luna)(ask.payload, choices, env, http)
            picker = ask.route
        except Exception as error:
            errors.append(f"{ask.route}: {error}")
    if purpose is None:
        purpose = utility_pick(choices, rng)
    thought = thought_for(purpose, rng)
    if ask.reflect and picker != "utility":
        calls["luna"] += 1
        calls["reflections"] += 1
        option = next(option for option in choices if option.name == purpose)
        try:
            thought = luna_reflect(ask.payload, option, env, http)
        except Exception as error:
            errors.append(f"reflection: {error}")
    return Choice(purpose, picker, thought, calls, "; ".join(errors) or None)


def deadline(ask: Ask) -> float:
    """Seconds after asking when an unanswered model call is given up: the pick's timeout (Jev
    20 s, Luna 45 s), plus Luna's for a reflection, plus 15 s."""
    seconds = JEV_TIMEOUT if ask.route == "jev" else LUNA_TIMEOUT
    return seconds + (LUNA_TIMEOUT if ask.reflect else 0.0) + GIVE_UP_AFTER


def apply_choice(state: dict, choice: Choice, now: float) -> None:
    """Make the choice the current purpose. A new purpose drops the old plan (or, during a reflex,
    the steps the reflex set aside) and ends a wait, or a sleep Mimo took while it waited for a
    choice, so the next tick plans at once."""
    brain = ensure_brain(state)
    changed = choice.purpose != brain["purpose"]
    brain.update(pending=None, picker=choice.picker, chosen_at=now, last_chosen=choice.purpose)
    if changed:
        brain.update(purpose=choice.purpose, batches=0, replans=0, planned_at=None,
                     handled_failure=state.get("last_failure"))
        if brain["reflex"] is not None:
            brain["set_aside"] = []
        else:
            state["queue"] = []
            action = state.get("action") or {}
            if action.get("kind") == "wait":
                state["action"] = None
            elif action.get("kind") == "sleep" and "purpose" not in action and choice.purpose != "sleep":
                record(state, action, now, "interrupted", "choice")
                state["action"] = None
    state["last_thought"] = choice.thought


def store_choice(world: SurvivalWorld, ask: Ask, choice: Choice, now: float) -> str | None:
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
            brain["model_calls"] = [*recent_model_calls(brain, ask.game_at), ask.game_at]
        pending = brain["pending"]
        fresh = pending is not None and pending["id"] == ask.pending_id
        if fresh:
            apply_choice(state, choice, now)
            purpose = PURPOSES.get(choice.purpose)
            phrase = purpose.phrase if purpose else choice.purpose.replace("_", " ")
            log_event(db, now, "purpose", f'{state["name"]} decided to {phrase}. "{choice.thought}"')
        write_state(db, state)
        return choice.purpose if fresh else None


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
        """Store a finished answer, or start answering a new pending choice. Returns the purpose stored."""
        now = time.time() if now is None else now
        if self.future is not None:
            return self.collect(now)
        life = registry.active_life()
        if life is None:
            return None
        path = registry.world_path(life)
        scale = time_scale() if self.scale is None else self.scale
        ask = prepare(SurvivalWorld(path, read_only=True), now, scale, self.env)
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
        return self.store(path, ask, Choice(purpose, "utility", thought_for(purpose, self.rng), calls, error), now)

    def store(self, path: Path, ask: Ask, choice: Choice, now: float) -> str | None:
        if choice.error:
            log_once(logger, "picker", ModelError(choice.error))
        return store_choice(SurvivalWorld(path), ask, choice, now)

    def close(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
