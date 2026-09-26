"""The worker's Talker (Bond): Mimo's side of its bond with the owner, outside the tick.

After each tick the worker polls the Chooser (purposes and goals) and then the Talker. The Talker
has lanes, each with a single background thread of its own, so a slow model call in one lane
never holds up another lane, the Chooser or the tick:
- "chat": the owner's lines waiting for Mimo's reply, oldest first (backend.survival.talk);
- "story": the diary entry due at the first game dawn after the owner's visit (B3,
  backend.survival.diary).
Each lane asks its providers (LANES[lane], first first) for a Job. A job the rules answer is
decided and stored at once; a model job is decided in the lane's thread while the worker keeps
ticking, and stored at a later poll. A job still unanswered `deadline` seconds after it was asked is
given up: its thread is left behind with its executor, a fresh one takes new work, and the job's
rules answer (`fallback`) is stored instead. At most one job a lane is started per poll. Preparing a
job (reading a snapshot, writing the options) runs in the worker's loop, as the Chooser's prepare does;
only the model call goes to the lane's thread. A job whose answer could not be stored rests its lane
for LANE_REST real seconds and keeps its answer: after the rest the same answer is stored again, so a
world that keeps refusing the write never costs another model call (`unstored`). A provider that
crashes while it looks for a job rests its lane for PROVIDER_REST real seconds, so a job that cannot
be built is not rebuilt every poll.
Every CHORE_EVERY real seconds the Talker also runs the chores (CHORES: the event log's mirrors,
backend.survival.events, first; then B2's asks and B3's inbox), rules only, in one short transaction
of their own; each chore runs in a savepoint, so one that
crashes is rolled back alone. The chores stop when a life ends, so the Talker closes an ended life
once (`close_life`: LAST_CHORES, the same way, Mind's last day among them), on its first poll and
whenever the active life changes or goes away. It reads the ended world's state first without
touching its files, and opens it for writing only when a last chore still has work there: an archive
nothing followed (a pet from before Mind) or one already closed is never written. Nothing here
raises: a crash is logged once and the worker goes on.
The Bond modules register their jobs and chores on import (backend.survival.bonding).
"""

from __future__ import annotations

import copy
import logging
import os
import sqlite3
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from backend.survival.clock import time_scale
from backend.survival.events import consumers, mirror_events
from backend.survival.models import Http, post_json
from backend.survival.once import log_once
from backend.survival.registry import LifeRegistry
from backend.survival.world import SurvivalWorld, WorldMissing, read_state, write_state

logger = logging.getLogger(__name__)

CHORE_EVERY = 5.0  # real seconds between two rounds of chores
LANE_REST = 60.0  # real seconds a lane rests after an answer could not be stored
PROVIDER_REST = 10.0  # real seconds a lane rests after one of its providers crashed
Env = Mapping[str, str]


@dataclass(frozen=True)
class Job:
    lane: str
    model: bool  # True: decided in the lane's thread (a model call); False: decided and stored at once
    asked_at: float
    deadline: float  # seconds after asked_at an unanswered job is given up
    decide: Callable[[Env, Http], object]  # the answer; never raises (a failed call gives the rules' answer)
    fallback: Callable[[], object]  # the rules' answer, for a job given up
    store: Callable[[SurvivalWorld, object, float], None]  # writes the answer in a short transaction of its own


# {lane: [provide(world, now, scale, env) -> Job | None]}: what each lane does, first first. `world`
# is read-only.
LANES: dict[str, list] = {"chat": [], "story": []}
# chore(db, state, now, scale) -> True when it changed the state: rules-only upkeep. The event log's
# mirrors come first (Mind hook R7: Mind's memories and B2's inbox register their writers there), then B2's
# and B3's chores.
CHORES: list = [mirror_events]
# (wanted(state) -> bool, chore(db, state, now, scale) -> True when it changed the state): rules-only,
# run once when a life has ended (`close_life`), in place of the CHORES that stop then (Mind: the events
# left to read, the last day). `wanted` says, from the ended world's state, whether the chore has work
# there; an ended world is opened for writing only when one does, so an archive is never written for
# nothing (a pet from before Mind, a life already closed).
LAST_CHORES: list = []
UNSEEN = object()  # the active life a new Talker has not looked at yet


def new_thread() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=1, thread_name_prefix="mimo-talker")


def each_chore(db, state: dict, chores: list, now: float, scale: float) -> bool:
    """Run `chores` in order, each in a savepoint, so a crash rolls back only its own writes and state
    changes (logged once). True when one changed the state."""
    changed = False
    for chore in chores:
        before = copy.deepcopy(state)
        db.execute("SAVEPOINT chore")
        try:
            changed = bool(chore(db, state, now, scale)) or changed
        except Exception as error:
            db.execute("ROLLBACK TO chore")
            state.clear()
            state.update(before)
            log_once(logger, f"chore {getattr(chore, '__name__', chore)}", error)
        db.execute("RELEASE chore")
    return changed


def run_chores(world: SurvivalWorld, now: float, scale: float) -> None:
    """Every chore once, in one transaction, while the life lasts."""
    chores = [chore for chore in CHORES if chore is not mirror_events or consumers()]  # mirrors with no one to tell
    if not chores:
        return
    with world.transaction() as db:
        state = read_state(db)
        if state["died_at"] is not None:
            return
        if each_chore(db, state, chores, now, scale):
            write_state(db, state)


def last_chores(state: dict) -> list:
    """The LAST_CHORES chores that still have work in an ended life with this state."""
    return [chore for wanted, chore in LAST_CHORES if wanted(state)]


def ended_state(path: Path) -> dict:
    """An ended life's state, read without changing any of its world's files. A world closed cleanly
    holds everything in its database file (its WAL is gone, or empty), so it is read as immutable:
    no lock is taken and no WAL or shared memory is opened, made or rebuilt. One whose WAL still has
    frames in it (a worker stopped mid-write) is read through that WAL, read-only."""
    path = Path(path)
    if not path.exists():
        raise WorldMissing(f"World database {path} is missing")
    wal = Path(f"{path}-wal")
    if wal.exists() and wal.stat().st_size:
        return SurvivalWorld(path, read_only=True).state()
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro&immutable=1", uri=True)
    try:
        db.row_factory = sqlite3.Row
        return read_state(db)
    finally:
        db.close()


def close_life(world: SurvivalWorld, now: float, scale: float) -> bool:
    """Every LAST_CHORES chore still wanted, once, in one transaction, for a life that has ended
    (nothing for one still alive). Each chore keeps its own "once" (Mind's state["mind"]["closed"]),
    so closing a life again changes nothing. True when a chore changed the state."""
    with world.transaction() as db:
        state = read_state(db)
        chores = last_chores(state) if state["died_at"] is not None else []
        if not chores:
            return False
        changed = each_chore(db, state, chores, now, scale)
        if changed:
            write_state(db, state)
        return changed


class Talker:
    """Answers the active life's Bond jobs, each lane's model calls in a background thread of its own.

    `executor_factory` makes each lane's executor, and the one that replaces an executor stuck on a
    hung call (tests pass one; the default is a new single-thread pool)."""

    def __init__(self, env: Env | None = None, http: Http = post_json,
                 executor_factory: Callable[[], object] | None = None, scale: float | None = None):
        from backend.survival import bonding, minding  # noqa: F401  (every Bond and Mind job and chore registers)
        self.env = os.environ if env is None else env
        self.http = http
        self.new_executor = executor_factory or new_thread
        self.executors: dict[str, object] = {}
        self.running: dict[str, tuple[Path, Job, Future]] = {}
        self.scale = scale
        self.chored_at: float | None = None
        self.resting: dict[str, float] = {}  # {lane: real time it may start a job again}
        self.unstored: dict[str, tuple[Path, Job, object]] = {}  # {lane: an answer to store again after the rest}
        self.active: object = UNSEEN  # the active life's id at the last poll (None: no pet alive)

    def executor(self, lane: str):
        if lane not in self.executors:
            self.executors[lane] = self.new_executor()
        return self.executors[lane]

    def poll(self, registry: LifeRegistry, now: float | None = None) -> None:
        now = time.time() if now is None else now
        life = registry.active_life()
        scale = time_scale() if self.scale is None else self.scale
        active = life["id"] if life is not None else None
        if active != self.active:  # the first poll, or the active life changed or went away
            self.active = active
            self.close_ended(registry, now, scale)
        if life is None:
            return
        path = registry.world_path(life)
        for lane in list(LANES):
            try:
                self.poll_lane(lane, path, now, scale)
            except Exception as error:
                log_once(logger, f"talker {lane}", error)
        if self.chored_at is None or now - self.chored_at >= CHORE_EVERY:
            self.chored_at = now
            try:
                run_chores(SurvivalWorld(path), now, scale)
            except Exception as error:
                log_once(logger, "talker chores", error)

    def close_ended(self, registry: LifeRegistry, now: float, scale: float) -> None:
        """Close the newest survival life that has ended (`close_life`; never the legacy life, which is
        only ever read). Its state is read first without touching its files (`ended_state`), and its
        world opened for writing only when a last chore still has work there, so a dead pet's archive
        from before Mind, or one already closed, stays byte for byte as it was."""
        try:
            ended = next((life for life in registry.list_lives()
                          if life["kind"] == "survival" and life["died_at"] is not None), None)
            if ended is None:
                return
            path = registry.world_path(ended)
            if last_chores(ended_state(path)):
                close_life(SurvivalWorld(path), now, scale)
        except Exception as error:
            log_once(logger, "talker close life", error)

    def poll_lane(self, lane: str, path: Path, now: float, scale: float) -> None:
        """Store the lane's finished job, give up a hung one, or start the next job."""
        if lane in self.running:
            where, job, future = self.running[lane]
            if future.done():
                del self.running[lane]
                try:
                    answer = future.result()
                except Exception as error:
                    log_once(logger, f"talker {lane} job", error)
                    answer = job.fallback()
                self.store(where, job, answer, now)
            elif now - job.asked_at > job.deadline:
                del self.running[lane]
                future.cancel()
                self.executor(lane).shutdown(wait=False, cancel_futures=True)
                self.executors[lane] = self.new_executor()
                log_once(logger, f"talker {lane}", TimeoutError(f"no answer after {job.deadline:g} s, gave up"))
                self.store(where, job, job.fallback(), now)
            return
        if now < self.resting.get(lane, 0.0):
            return
        if lane in self.unstored:  # the answer is kept: store it again rather than ask the model again
            where, job, answer = self.unstored.pop(lane)
            self.store(where, job, answer, now)
            return
        world = SurvivalWorld(path, read_only=True)
        for provide in LANES[lane]:
            try:
                job = provide(world, now, scale, self.env)
            except Exception as error:
                log_once(logger, f"talker {lane} provider {getattr(provide, '__name__', provide)}", error)
                self.resting[lane] = now + PROVIDER_REST
                return
            if job is None:
                continue
            if job.model:
                future = self.executor(lane).submit(job.decide, self.env, self.http)
                self.running[lane] = (path, job, future)
                if future.done():  # an inline executor (tests, the rules) answered at once
                    self.poll_lane(lane, path, now, scale)
            else:
                self.store(path, job, job.decide(self.env, self.http), now)
            return

    def store(self, path: Path, job: Job, answer: object, now: float) -> None:
        """Store a job's answer; one that cannot be stored is kept, and its lane rests before trying again."""
        try:
            job.store(SurvivalWorld(path), answer, now)
        except Exception as error:
            log_once(logger, f"talker {job.lane} store", error)
            self.resting[job.lane] = now + LANE_REST
            self.unstored[job.lane] = (path, job, answer)

    def close(self) -> None:
        for executor in self.executors.values():
            executor.shutdown(wait=False, cancel_futures=True)
