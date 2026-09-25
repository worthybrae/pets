"""The knowledge journal (L4b, the owner's day-17 note: "I want it to be more curious and
constantly exploring and trying to undestand the world").

The first time Mimo meets a kind of block, plant, creature, biome or landmark that the rules table
(LESSONS) has a lesson for, it studies it and learns what it teaches: "gravel sometimes hides
flint", "skitters come out of caves at night". A lesson is remembered in memory_knowledge (fact
"lesson", with when), logged as a routine "learned" event ("Pip learned that gravel sometimes hides
flint.") and is a discovery for curiosity (NEW_LESSON); one that unlocks something asks for a new
choice. The journal starts with curiosity, once the tick first tends it (`observe_journal`, from
brain.observe_step, does nothing before). Studying takes one of three forms:
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
  investigate is day work in the work band: 40 plus a quarter of curiosity, minus late.

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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.services.worldgen import SEA_LEVEL, biome_at, surface_material, terrain_height
from backend.survival.clock import DAY_SECONDS
from backend.survival.curiosity import discovered
from backend.survival.grid import Cell
from backend.survival.memory import cell_of, forget, know, places, remember
from backend.survival.once import log_once
from backend.survival.senses import natural_plants
from backend.survival.steps import as_cell
from backend.survival.triggers import ensure_brain, mark_trigger

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

FACT = "lesson"  # the memory_knowledge fact for a lesson learned
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
    thing: str  # a block, plant, creature or biome name, or a landmark ("cave_mouth", "sinkhole", "lake")
    kind: str  # "block", "plant", "creature", "biome" or "landmark"
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
    Lesson("sand", "block", "sand", "Sand lies in the desert and under the lakes, and cactus grows on it.", "",
           ("Sand everywhere in the desert, and under the water too.", "Soft sand. Cactus likes it.")),
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
    """The lessons Mimo learned, (thing, when), first first."""
    rows = db.execute("SELECT subject, learned_at FROM memory_knowledge WHERE fact=? ORDER BY learned_at, subject",
                      (FACT,)).fetchall()
    return [(row[0], row[1]) for row in rows]


def learn_lesson(state: dict, context: ActionContext, at: float, thing: str) -> bool:
    """Learn the lesson `thing` teaches, the first time: remembered, logged, a discovery for
    curiosity, and a new choice asked for when it unlocks something. True the first time."""
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
    discovered(state, at, NEW_LESSON)
    if lesson.unlocks:
        mark_trigger(state, "discovery", at)
    return True


# Meeting things --------------------------------------------------------------------------------

def taught(db, thing: str) -> bool:
    return thing in LESSONS and db.execute("SELECT 1 FROM memory_knowledge WHERE subject=? AND fact=?",
                                           (thing, FACT)).fetchone() is not None


def note_sights(state: dict, context: ActionContext, at: float) -> None:
    """Look over the ground around Mimo after a walk: the first of each kind of surface block or
    plant with a lesson it has not learned is remembered as a sight."""
    db, seed = context.db, state["world_seed"]
    x, _, z = as_cell(state["position"])
    sighted = {place["note"] for place in places(db, ("sight",))}
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
        if thing not in sighted and not taught(db, thing):
            remember(db, "sight", cell, at, thing)


def observe_journal(state: dict, step: dict, context: ActionContext, at: float) -> None:
    """After a finished step (brain.observe_step): what Mimo learns there and then, what it sees to
    study later, and the end of a look or a watch. The journal starts with curiosity, once the tick
    first tends it (curiosity.tend_curiosity)."""
    db = context.db
    if db is None or "curiosity" not in ensure_brain(state):
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
