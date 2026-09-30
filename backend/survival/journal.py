"""The knowledge journal (L4b, the owner's day-17 note: "I want it to be more curious and
constantly exploring and trying to undestand the world").

The first time Mimo meets a kind of block, plant, creature, biome or landmark that the rules table
(LESSONS) has a lesson for, it studies it and learns what it teaches: "gravel sometimes hides
flint", "skitters come out of caves at night". A lesson is remembered in memory_knowledge (fact
"lesson", with when), logged as a routine "learned" event ("Pip learned that gravel sometimes hides
flint.") and is a discovery for curiosity (NEW_LESSON; the L4b final fix wave's follow-up 2: like
new ground, a lesson never takes curiosity below curiosity.GROUND_FLOOR, though it still counts as
a discovery); one that unlocks something asks for a new choice. The journal starts with
curiosity, once the tick first tends it (`observe_journal`, from brain.observe_step, does nothing
before). Studying takes one of three forms:
- Mimo learns at once what it meets right there: a kind of block it digs (the sample is in its
  arms), an ore or lava its digging lays bare beside it, the biome it walks into, and a cave mouth,
  sinkhole or lake it walks up to (a remembered cave or water place within LANDMARK_NEAR blocks).
- What it only sees from a walk it goes back to: after each walk it looks over the ground around
  it (every other column within SIGHT_RADIUS) for surface blocks with a lesson (gravel, sand, snow,
  mud, moss) and the plants too (sugar cane, pumpkins, melons, brown mushrooms, cactus), and
  remembers the first of each kind as a "sight" place, noted with what it is.
- The `investigate` purpose walks up to the nearest thing it has not learned about yet within
  INVESTIGATE_REACH blocks (a sight, or a creature of a kind it met, curiosity's "creature" facts,
  within CREATURE_SIGHT), looks it over and takes a sample: it mines a block it can dig (never
  something it built or tends, and never with water over it), or watches a creature for
  WATCH_SECONDS; a plant it looks over. The lesson is learned when the look (a wait of
  LOOK_SECONDS, or the watch) ends. A thing an investigation failed on is left alone for TRIED_FOR.
  investigate is day work in the work band: 40 plus a quarter of curiosity, minus late. L4b final fix
  wave, I5: it has an urge (goals.URGES) while there is something to study, so from curiosity 40,
  where its score reaches goals.NEED_FLOOR, it meets a need and goal work does not crowd it out (it
  rarely won against L4a's goal steering: plants 8 blocks from home went unstudied for days); a
  sated pet (under 40) still studies only when nothing for its goal is on offer. A sight remembered
  farther than INVESTIGATE_REACH from where Mimo is gives way to a new sighting of its kind, so one
  noted 150 blocks out on a trip no longer keeps the same thing near home from being noted.

Knowledge unlocks behaviour, so learning has a purpose (Situation.lessons): gather_flint digs
gravel only once Mimo learned that gravel hides flint, and mine_ore goes after gold and diamonds
only once it has seen their ore.

Jev may phrase a lesson's journal line in Mimo's voice. Jev's API answers choices, so each lesson
carries a few phrasings (`lines`) and the worker asks Jev to choose the one that fits (never in the
tick or in tests without a fake; backend.survival.choosing). Until then the journal shows the fact.
The brain keeps state["brain"]["journal"]: {"studying": {"thing", "cell"} or None, "tried": {thing:
server time}, "words": {thing: the line Jev chose}, "unphrased": [things learned and not yet
phrased]}.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.services.crafting import can_harvest
from backend.services.worldgen import SEA_LEVEL, biome_at, surface_material, terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.creatures.table import dead
from backend.survival.curiosity import GROUND_FLOOR, discovered, seen, value_of
from backend.survival.foraging import reach_steps, whole_walk
from backend.survival.goals import add_urge
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, forget, know, places, remember
from backend.survival.once import log_once
from backend.survival.purposes import Purpose, late_penalty, register
from backend.survival.senses import natural_plants, near_failure
from backend.survival.situation import Situation
from backend.survival.steps import as_cell
from backend.survival.structures import reserved
from backend.survival.triggers import ensure_brain, mark_trigger
from backend.survival.wild import BORN_KNOWING, KIND as SURVIVAL_KIND, SURVIVAL, thing as survival_thing

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

FACT = "lesson"  # the memory_knowledge fact for a lesson learned
TAUGHT = "taught"  # Mind M2: the memory_knowledge fact for a lesson the owner taught (backend.survival.teaching)
NEW_LESSON = 5.0  # curiosity a lesson takes away
INVESTIGATE_REACH = 32.0
CREATURE_SIGHT = 24.0
WATCH_REACH = 4.0
LOOK_SECONDS = 4.0  # game seconds Mimo looks a thing over
WATCH_SECONDS = 8.0  # game seconds it watches a creature
TRIED_FOR = DAY_SECONDS / 2  # game seconds a thing an investigation failed on is left alone
SIGHT_RADIUS = 6  # columns this far around the end of a walk are looked over
PLANT_SIGHT = 8.0
LANDMARK_NEAR = 8.0


@dataclass(frozen=True)
class Lesson:
    # a block, plant, creature or biome name, a landmark ("cave_mouth", "sinkhole", "lake"), a making lesson
    # ("copper_spark", "clock") or one of Mind's ("recipe:bow", "cow:drops")
    thing: str
    kind: str  # "block", "plant", "creature", "biome", "landmark", "recipe" (Mind), "making" or "survival" (W1)
    words: str  # "gravel", "a sheep"
    fact: str  # "Gravel sometimes hides flint."
    unlocks: str = ""  # what it lets Mimo do: "digs gravel for flint"
    lines: tuple[str, ...] = ()  # the journal line in Mimo's voice, for Jev to choose among


LESSONS: dict[str, Lesson] = {}


def teach(*lessons: Lesson) -> None:
    for lesson in lessons:
        LESSONS[lesson.thing] = lesson


teach(
    Lesson("gravel", "block", "gravel", "Gravel sometimes hides flint.", "digs gravel for flint",
           ("Dig enough gravel and a flint turns up. Arrows!", "Gravel crunches, and there was flint inside!")),
    Lesson("sand", "block", "sand", "Sand lies in the desert, on shores and under the lakes, and cactus grows on it.",
           "", ("Sand everywhere in the desert, and under the water too.", "Soft sand. Cactus likes it.")),
    Lesson("snow", "block", "snow", "Snow lies on the cold taiga and high in the mountains.", "",
           ("Cold, white and crunchy: snow.", "Snow only lies where it is cold.")),
    Lesson("mud", "block", "mud", "Mud lies wet in the swamp.", "",
           ("Squelch. The swamp is all mud.", "Mud, wet and sticky, all over the swamp.")),
    Lesson("moss", "block", "moss", "Moss grows on the forest floor.", "",
           ("Soft green moss under the trees.", "The forest floor is mossy in places.")),
    Lesson("coal_ore", "block", "coal ore", "Coal burns: a coal and a stick make four torches.", "",
           ("One coal and one stick: four torches!", "Coal is for light. I'll keep some.")),
    Lesson("iron_ore", "block", "iron ore", "Iron ore needs a stone pickaxe, and a furnace turns it into iron.", "",
           ("Iron! It needs a stone pickaxe and a hot furnace.", "Iron ore: dig it with stone, melt it in a furnace.")),
    Lesson("gold_ore", "block", "gold ore", "Gold lies deep, takes an iron pickaxe to dig and a furnace to melt.",
           "goes after gold",
           ("Gold, deep down! An iron pickaxe will get it.", "Shiny gold in the rock. I'll be back.")),
    Lesson("diamond_ore", "block", "diamond ore", "Diamonds lie deepest of all, and an iron pickaxe digs them.",
           "goes after diamonds",
           ("A diamond! The deepest treasure of all.", "Diamonds sparkle down here. Iron will dig them.")),
    Lesson("lava", "block", "lava", "Lava glows in the dark caves, and it burns whatever falls in.", "",
           ("Lava lights up the caves. Never, ever step in it.", "Glowing, bubbling lava. Stay well back.")),
    Lesson("sugar_cane", "plant", "sugar cane", "Sugar cane grows only beside water.", "",
           ("Sugar cane, right at the water's edge.", "Tall canes, and always by the water.")),
    Lesson("pumpkin", "plant", "a pumpkin", "Pumpkins grow wild in the grass.", "",
           ("A wild pumpkin, big and round!", "Pumpkins just grow here on their own.")),
    Lesson("melon", "plant", "a melon", "Melons grow wild in the grass.", "",
           ("A wild melon. Sweet!", "Melons grow on their own out here.")),
    Lesson("brown_mushroom", "plant", "a brown mushroom", "Brown mushrooms grow in the shade.", "",
           ("Brown mushrooms like the shade.", "Little brown mushrooms, hiding in the shadows.")),
    Lesson("cactus", "plant", "a cactus", "Cactus grows only on sand, and it pricks.", "",
           ("Ouch, prickly! Cactus only grows on sand.", "A cactus. Look, don't touch.")),
    Lesson("rabbit", "creature", "a rabbit", "Rabbits are quick, and four of their hides make leather.", "",
           ("Rabbits are so fast! Their hides make leather.", "A rabbit. Four hides and I'd have leather.")),
    Lesson("chicken", "creature", "a chicken",
           "Chickens drop feathers, and a feather, a flint and a stick make arrows.", "",
           ("Chickens drop feathers. Feathers make arrows fly!", "Feathers from chickens, for my arrows.")),
    Lesson("sheep", "creature", "a sheep", "Sheep give mutton and wool.", "",
           ("Sheep are fluffy: wool, and mutton too.", "Woolly sheep, grazing. Mutton for later.")),
    Lesson("cow", "creature", "a cow", "Cows give beef, and leather for a cap and a tunic.", "",
           ("Cows: beef, and leather for armor.", "A big cow. Leather would make a tunic.")),
    Lesson("fish", "creature", "a fish", "Fish swim in the lakes and rivers.", "",
           ("Fish, darting in the water!", "There are fish in the water here.")),
    Lesson("gloomling", "creature", "a gloomling",
           "Gloomlings come out in the dark and hit hard; light keeps them away.",
           "", ("Gloomlings hate the light. Torches keep them off.", "A gloomling! They come with the dark.")),
    Lesson("skitter", "creature", "a skitter", "Skitters come out of caves at night.", "",
           ("Skitters crawl out of the caves at night.", "Skitters live in the caves. Careful after dark.")),
    Lesson("meadow", "biome", "a meadow", "Meadows are open grass, easy to walk and to build on.", "",
           ("Open meadow, easy to walk, good to build on.", "A meadow: flat, grassy and wide.")),
    Lesson("forest", "biome", "a forest", "Forests are full of oak for wood.", "",
           ("Oaks everywhere! Plenty of wood.", "A forest: all the wood I could want.")),
    Lesson("birch_forest", "biome", "a birch forest", "Birch forests grow pale birch wood.", "",
           ("Pale birch trees, all in a row.", "Birch wood grows here, white and straight.")),
    Lesson("taiga", "biome", "the taiga", "The taiga is cold, with spruce, snow and gravel.", "",
           ("The taiga: cold, snowy, full of spruce.", "Spruce and snow and gravel. Brr, the taiga.")),
    Lesson("swamp", "biome", "a swamp", "Swamps are wet and muddy.", "",
           ("A swamp, all mud and puddles.", "Wet feet in the swamp.")),
    Lesson("desert", "biome", "a desert", "The desert is dry sand where cactus grows and little else.", "",
           ("Hot, dry desert. Not much to eat here.", "Sand and cactus as far as I can see.")),
    Lesson("alpine", "biome", "the mountains", "The mountains are high and cold, with gravel in their scree.", "",
           ("Up in the mountains, cold and high.", "Mountains! Snowy tops and gravel slopes.")),
    Lesson("cave_mouth", "landmark", "a cave mouth",
           "Cave mouths lead down into the dark, where ores show in the walls.",
           "", ("A cave mouth. Ores hide in the dark down there.", "The cave goes down and down.")),
    Lesson("sinkhole", "landmark", "a sinkhole", "Sinkholes drop straight down into the caves.", "",
           ("A sinkhole, straight down into the caves!", "Careful: this hole drops right into a cave.")),
    Lesson("lake", "landmark", "a lake", "Lakes hold fish, and gravel lines their beds.", "",
           ("A lake! Fish in it, gravel under it.", "Water, fish, and gravel on the bottom.")),
)
# W1: the survival lessons a wild pet learns from its owner or alone (backend.survival.wild).
teach(*(Lesson(survival_thing(lesson.name), SURVIVAL_KIND, lesson.words, lesson.fact, lesson.unlocks)
        for lesson in SURVIVAL))
SURFACE = tuple(name for name, lesson in LESSONS.items() if lesson.kind == "block")
PLANTS = tuple(name for name, lesson in LESSONS.items() if lesson.kind == "plant")
LANDMARKS = {"mouth": "cave_mouth", "sinkhole": "sinkhole"}


def journal_state(state: dict) -> dict:
    """The brain's journal, with the fields a world from before L4b lacks."""
    journal = ensure_brain(state).setdefault("journal", {})
    journal.setdefault("studying", None)
    journal.setdefault("tried", {})
    journal.setdefault("words", {})
    journal.setdefault("unphrased", [])
    return journal


def learned(db) -> list[tuple[str, float]]:
    """The lessons Mimo learned, (thing, when), first first; W1: not those it knew from the start."""
    rows = db.execute("SELECT subject, learned_at FROM memory_knowledge WHERE fact=? AND subject NOT IN "
                      "(SELECT subject FROM memory_knowledge WHERE fact=?) ORDER BY learned_at, subject",
                      (FACT, BORN_KNOWING)).fetchall()
    return [(row[0], row[1]) for row in rows]


def learn_lesson(state: dict, context: ActionContext, at: float, thing: str) -> bool:
    """Learn the lesson `thing` teaches, the first time: remembered, logged, a discovery for
    curiosity, and a new choice asked for when it unlocks something. True the first time.
    Follow-up 2 (F1 of the scoped re-review): like new ground, a lesson never takes curiosity below
    GROUND_FLOOR, the expedition's gate. With investigate an urge from 40 (I5), each lesson took 5
    off and a pet near home kept studying itself back under the gate: at sim pace 4 of 9 rules pets
    made no expedition in 8 game days, where all 9 had."""
    lesson, db = LESSONS.get(thing), context.db
    if lesson is None or db is None or not know(db, thing, FACT, at):
        return False
    fact = lesson.fact
    context.events.append((at, "learned", f"{state['name']} learned that {fact[:1].lower()}{fact[1:]}"))
    journal = journal_state(state)
    journal["unphrased"] = [*journal["unphrased"], thing]
    for place in places(db, ("sight",)):
        if place["note"] == thing:
            forget(db, "sight", cell_of(place))
    discovered(state, at, min(NEW_LESSON, max(0.0, value_of(state["brain"]) - GROUND_FLOOR)))
    if lesson.unlocks:
        mark_trigger(state, "discovery", at)
    return True


# Meeting things --------------------------------------------------------------------------------

def taught(db, thing: str) -> bool:
    return thing in LESSONS and db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact=?",
                                           (thing, FACT)).fetchone() is not None


def note_sights(state: dict, context: ActionContext, at: float) -> None:
    """Look over the ground around Mimo after a walk: the first of each kind of surface block or
    plant with a lesson it has not learned is remembered as a sight. The final fix wave, I5: a sight
    of that kind remembered out of reach (farther than INVESTIGATE_REACH from here) gives way to it."""
    db, seed = context.db, state["world_seed"]
    x, _, z = as_cell(state["position"])
    sights = places(db, ("sight",))
    sighted = {place["note"] for place in sights}
    far = {place["note"]: place for place in sights if math.hypot(place["x"] - x, place["z"] - z) > INVESTIGATE_REACH}
    fresh: dict[str, Cell] = {}
    for dx in range(-SIGHT_RADIUS, SIGHT_RADIUS + 1, 2):
        for dz in range(-SIGHT_RADIUS, SIGHT_RADIUS + 1, 2):
            gx, gz = x + dx, z + dz
            height = terrain_height(gx, gz, seed)
            material = surface_material(gx, gz, seed) if height >= SEA_LEVEL else ""
            if material in SURFACE and context.grid.material(gx, height, gz) == material:
                fresh.setdefault(material, (gx, height, gz))
    for cell in natural_plants(seed, x, z, PLANT_SIGHT, PLANTS):
        material = context.grid.material(*cell)
        if material in PLANTS:
            fresh.setdefault(material, cell)
    for thing, cell in sorted(fresh.items()):
        if thing in far and not taught(db, thing):  # I5: out of reach there, in sight here
            forget(db, "sight", cell_of(far[thing]))
            sighted.discard(thing)
        if thing not in sighted and not taught(db, thing):
            remember(db, "sight", cell, at, thing)


def journal_ready(state: dict, db: sqlite3.Connection | None) -> bool:
    """Whether the journal does anything yet: not before there is memory to write to, and not
    before the tick first tends curiosity (curiosity.tend_curiosity). The guard observe_journal
    uses, shared with any other path that teaches a lesson outside a finished step (life_goals'
    iron_look, fix round 1: ore seen through a cave opening)."""
    return db is not None and "curiosity" in ensure_brain(state)


def observe_journal(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a finished step (brain.observe_step): what Mimo learns there and then, what it sees to
    study later, and the end of a look or a watch. The journal starts with curiosity, once the tick
    first tends it (curiosity.tend_curiosity)."""
    db = context.db
    if not journal_ready(state, db):
        return
    try:
        kind = step["kind"]
        journal = journal_state(state)
        if kind == "mine":
            cell = as_cell(step["target"])
            learn_lesson(state, context, at, step.get("block", ""))
            x, y, z = cell
            for near in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)):
                material = context.grid.material(*near)
                if material == "lava" or material.endswith("_ore"):
                    learn_lesson(state, context, at, material)
        elif kind in ("walk", "swim"):
            x, _, z = as_cell(state["position"])
            learn_lesson(state, context, at, biome_at(x, z, state["world_seed"]))
            for place in places(db, ("cave", "water"), around=(x, 0, z), reach=LANDMARK_NEAR):
                if math.hypot(place["x"] - x, place["z"] - z) <= LANDMARK_NEAR:
                    thing = "lake" if place["kind"] == "water" else LANDMARKS.get(place["note"], "")
                    learn_lesson(state, context, at, thing)
            note_sights(state, context, at)
        elif kind == "wait" and step.get("purpose") == "investigate" and journal["studying"]:
            learn_lesson(state, context, at, journal["studying"]["thing"])
            journal["studying"] = None
    except Exception as error:
        log_once(logger, "journal", error)


# investigate -----------------------------------------------------------------------------------

def note_failure(state: dict, at: float) -> None:
    """An investigation failed: what it was after is left alone for a while."""
    journal = journal_state(state)
    if journal["studying"]:
        journal["tried"] = {**journal["tried"], journal["studying"]["thing"]: at}
        journal["studying"] = None


@dataclass(frozen=True)
class Curio:
    thing: str
    cell: Cell
    creature: bool = False


def lessons_of(s: Situation) -> set[str]:
    return set(s.lessons)


def tried_lately(s: Situation, thing: str) -> bool:
    tried = (s.brain.get("journal") or {}).get("tried", {}).get(thing)
    return tried is not None and (s.at - tried) * s.scale < TRIED_FOR


def curios(s: Situation) -> list[Curio]:
    """What Mimo could go and study now, nearest first: sights within INVESTIGATE_REACH that are
    still there, and creatures of kinds it met but has not studied, within CREATURE_SIGHT."""
    def look() -> list[Curio]:
        known_now = lessons_of(s)
        found = []
        for place in s.places:
            thing, cell = place["note"], cell_of(place)
            if (place["kind"] != "sight" or thing not in LESSONS or thing in known_now or tried_lately(s, thing)
                    or s.distance(cell) > INVESTIGATE_REACH or s.grid.material(*cell) != thing
                    or near_failure(s.state, cell)):
                continue
            found.append(Curio(thing, cell))
        unmet = {kind for kind in seen(s, "creature") if kind in LESSONS and kind not in known_now
                 and not tried_lately(s, kind)}
        herd = s.grid.herd
        if unmet and herd is not None:
            x, _, z = s.here
            for creature in herd.near(x, z, CREATURE_SIGHT):
                if creature["kind"] in unmet and not dead(creature) and "x" in creature:
                    cell = (round(creature["x"]), round(creature.get("y", s.here[1])), round(creature["z"]))
                    found.append(Curio(creature["kind"], cell, creature=True))
                    unmet.discard(creature["kind"])
        return sorted(found, key=lambda curio: (s.distance(curio.cell), curio.thing))
    return s.sensed("curios", look)


def diggable(s: Situation, cell: Cell) -> bool:
    """A block Mimo may take a sample of: one it can harvest with what it carries, with no water
    over it, that it neither built nor tends."""
    x, y, z = cell
    material = s.grid.material(*cell)
    return (can_harvest(material, s.inventory) and s.grid.material(x, y + 1, z) != "water"
            and not reserved(s.grid, cell) and not s.grid.thick_ice(cell))  # W2: a lake's ice is too thick


def investigate_valid(s: Situation) -> bool:
    return not s.night and bool(curios(s))


def investigate_score(s: Situation) -> float:
    return max(0.0, 40.0 + value_of(s.brain) / 4 - late_penalty(s))


def plan_investigate(s: Situation, context: ActionContext) -> list[dict]:
    """Walk up to the nearest curio, sample it and look it over. One batch: once it is done the
    lesson is learned (observe_journal) and the purpose ends."""
    if s.brain["replans"] > 0:  # the walk or the sample failed: leave that thing alone for a while
        note_failure(s.state, s.at)
        return []
    if s.brain["batches"] > 0 or not curios(s):
        return []
    curio = curios(s)[0]
    journal_state(s.state)["studying"] = {"thing": curio.thing, "cell": list(curio.cell)}
    if curio.creature:
        walk = [whole_walk(curio.cell, WATCH_REACH)] if s.distance(curio.cell) > WATCH_REACH else []
        return [*walk, {"kind": "wait", "seconds": max(1.0, WATCH_SECONDS / s.scale)}]
    look = {"kind": "wait", "seconds": max(1.0, LOOK_SECONDS / s.scale)}
    sample = [{"kind": "mine", "target": list(curio.cell)}] if LESSONS[curio.thing].kind == "block" and diggable(
        s, curio.cell) else []
    return reach_steps(s, [(curio.cell, [*sample, look])])


def investigate_facts(s: Situation) -> str:
    found = curios(s)
    nearest = found[0]
    return (f"{len(found)} things it has never studied nearby; the nearest is {LESSONS[nearest.thing].words} "
            f"{round(s.distance(nearest.cell))} blocks away; {len(lessons_of(s))} lessons learned")


# The final fix wave, I5: a need while there is something to study (with the score as it is, from
# curiosity 40: goals.meets_need asks for NEED_FLOOR), so goal work does not crowd it out.
add_urge("investigate", lambda s: bool(curios(s)))


register(Purpose(
    "investigate", "take a closer look",
    "Walk up to something new nearby, look it over and take a sample, to learn what it is good for.",
    valid=investigate_valid, facts=investigate_facts, score=investigate_score, plan=plan_investigate,
    thoughts=("What is that? I have to look closer.", "I've never seen one of those before.")))


# What the model and the viewer are told --------------------------------------------------------

def journal_view(db, brain: dict | None, limit: int = 40) -> list[dict]:
    """The lessons Mimo learned, newest first: {thing, kind, fact, line (Jev's pick, or the fact),
    unlocks, at, from_you (Mind M2: the owner taught it), source (W1: "from_you", "figured" or
    "from_start")}. A world from before L3 read as an archive has learned nothing. W1: the survival lessons
    are listed apart, known or not (wild.survival_view), so they are left out here."""
    words = ((brain or {}).get("journal") or {}).get("words", {})
    try:
        rows = learned(db)
        # fix round 1, Minor 9: "from_owner", not "taught" -- that name already means journal.taught()
        from_owner = {row[0] for row in db.execute("SELECT subject FROM memory_knowledge WHERE fact=?", (TAUGHT,))}
    except sqlite3.OperationalError:  # no memory_knowledge table: an archive from before L3
        return []
    found = []
    for name, at in reversed(rows):
        lesson = LESSONS.get(name)
        if lesson is None or lesson.kind == SURVIVAL_KIND:
            continue
        found.append({"thing": name, "kind": lesson.kind, "words": lesson.words, "fact": lesson.fact,
                      "line": words.get(name) or lesson.fact, "unlocks": lesson.unlocks, "at": at,
                      "from_you": name in from_owner, "source": "from_you" if name in from_owner else "figured"})
    return found[:limit]


def journal_payload(s: Situation) -> dict:
    """For the model: how many lessons Mimo learned, the newest, and what it could study near it."""
    known_now = sorted(lessons_of(s))
    newest = learned(s.db)[-1][0] if s.db is not None and known_now else None
    return {"lessons": len(known_now), "newest": LESSONS[newest].fact if newest in LESSONS else None,
            "could_study": [LESSONS[curio.thing].words for curio in curios(s)[:3]]}
