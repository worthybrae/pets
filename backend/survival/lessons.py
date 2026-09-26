"""Lessons the owner can teach (Mind M2): every armor, tool and weapon recipe, and every creature.

L4b's journal (backend.survival.journal) has lessons Mimo learns by meeting things. Mind adds
lessons written from the game's own tables, so what they say is always true:
- a recipe lesson for every armor, tool and weapon recipe in backend.services.crafting.RECIPES
  (`gear_group`: a pickaxe or an axe is a tool; a sword, a bow or arrows a weapon; a cap or a
  tunic armor), from its ingredients, what it makes and where: "An iron sword takes two iron
  ingots and a stick, at a crafting table." (kind "recipe", thing "recipe:iron_sword"). Part B's
  recipes join by name with `teach_recipe`;
- two creature lessons for every kind in the creature registry: what it drops, from its drop table
  ("A cow drops one to three raw beef and up to two leather.", "cow:drops"; none for a kind that
  drops nothing), and how it lives, from its biomes and herds or, for a hostile kind, HABITS ("Cows
  graze in meadows, forests, birch forests and swamps, two to three together.", "cow:habits").
Nothing in the world teaches these; the owner does, through the chat (backend.survival.teaching).
Their things hold a colon, so they are never things to go and study (journal.curios looks for
L4b's block, plant and creature names). They unlock nothing: L4b's lessons keep their own gates
(gravel's flint, gold, diamonds) and Part B's "copper carries a spark" brings its own.

`claims(text)` reads the owner's words against every lesson in journal.LESSONS, one sentence at a
time (a false or foreign word in one sentence never spoils a lesson a later sentence teaches
cleanly: "I like the lake. Skitters hate light." still teaches the skitter lessons). A lesson fits
a sentence when its words name what the lesson is about (one of its `subjects`: "iron sword", or
"iron armor" for iron armor, TEACH_SYNONYMS widening them), say something it says too (another of
its `words`), and name no other thing of the world (mind.vocabulary) that it does not: "cows give
leather" fits the cow lessons, "cows give diamonds" fits none, since no cow lesson speaks of
diamonds, and is `doubtful`.

A short statement that starts by naming a known subject (a creature kind or a recipe item) and is
directly followed by a claim no lesson supports at all is `doubtful` too, even when its verb is
outside TEACH_VERBS: "cows fly", "cows fly, it is true" (controller ruling, Task 5 and Task 6
review). A copula right after the subject only describes it ("cows are cute", "cows are cute and
friendly", both describing words) unless a non-describing word follows too ("skitters are friendly
and sing", still doubtful); a word that only exclaims or observes ("cows look happy today", "cows
rule!", "cow spotted near the lake") or a comma right after the subject (an exclamation or address:
"skitters, yikes", "chickens, chickens everywhere") never is either, nor is talk of the owner ("I",
"you", "we", "my", "your", "let's", "me", "us", "our", "mine", "u", "he", "him", "she", "her",
"they", "them"), checked on the raw words ("Moss, I love you", the pet named after the moss
lesson's own subject) -- nor is anything that does not start with the subject at all ("good morning
cows", "nice sword!", a place or a compliment mentioned in passing). Words that seem to teach about
things no lesson is about are `unknown`, narrowed the same way: "bread is made from wheat" stays
unknown ("bread" is a thing), "keep the torch lit" does not ("keep" is not). A question never
teaches.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.services.crafting import RECIPES
from backend.survival.creatures.kinds import KINDS, Kind
from backend.survival.journal import LESSONS, Lesson, teach
from backend.survival.mind import singular, vocabulary, words_of

SHORTLIST = 5  # lessons offered for one line
NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
GROUPS = (("tool", ("_pickaxe", "_axe")), ("weapon", ("_sword", "bow", "arrow")), ("armor", ("_cap", "_tunic")))
# Ingredients that are not counted one by one ("three string", "two leather").
MASS = frozenset({"string", "leather", "cobblestone", "raw_beef", "raw_mutton", "wool", "gloom_dust"})
PLURAL = {"sheep": "sheep", "fish": "fish"}
LANDS = {"meadow": "meadows", "forest": "forests", "birch_forest": "birch forests", "taiga": "the taiga",
         "swamp": "swamps", "desert": "deserts", "alpine": "the mountains"}
# How the passive kinds live; a new kind without words here is described from its table alone.
WAYS = {"rabbit": "hop about", "chicken": "peck about", "sheep": "graze", "cow": "graze", "fish": "swim"}
# How the hostile kinds live (as backend.survival.creatures.hostiles has them).
HABITS = {
    "gloomling": "Gloomlings walk dark ground at night and the caves at any hour, and the sun burns them up.",
    "skitter": "Skitters live in the caves and dark places, and the sunlight makes them fade.",
}
# Words that mean the same in the owner's mouth, both ways.
TEACH_SYNONYMS = (
    {"cap", "helmet", "hat"}, {"tunic", "shirt", "chestplate"}, {"pickaxe", "pick"}, {"sword", "blade"},
    {"cow", "cattle"}, {"skitter", "spider"}, {"gloomling", "zombie"}, {"rabbit", "bunny"},
    {"give", "drop"}, {"take", "need", "cost"}, {"make", "made", "craft"}, {"dark", "light", "shadow", "night"},
    {"sun", "sunlight", "day", "daylight", "light"}, {"fade", "burn"}, {"mountain", "alpine"},
    {"ingot", "bar"}, {"wooden", "wood"}, {"stone", "cobblestone"},
)
TEACH_VERBS = frozenset({"give", "make", "made", "need", "take", "drop", "come", "live", "grow", "burn", "hide",
                         "keep", "craft", "dig", "smelt", "cook", "spawn", "hate", "fear", "use", "turn", "melt"})
QUESTION_WORDS = frozenset({"do", "does", "did", "can", "could", "is", "are", "was", "what", "how", "why", "where",
                            "when", "who", "which", "should", "would", "will"})
# "cows are cute": a copula right after a known subject only describes it, not a claim to check,
# unless more follows too ("skitters are friendly and sing", controller ruling, Task 6 review); "X
# are A and B", both describing words, is chat too, even with more than one ("cows are cute and
# friendly", fix round 2, residual 7). Fillers ("so", "very") are already STOPWORDS.
COPULA = frozenset({"is", "are", "was", "were"})
DESCRIBING = frozenset({"cute", "fluffy", "friendly", "soft", "happy", "big", "small", "scary", "nice", "funny",
                        "lovely", "sweet", "fat", "loud", "quiet", "fast", "slow"})
# Talk of the owner, not a claim about the subject ("Moss, I love you", "let's go fishing", "cows
# love u"), checked on the raw words (the pet's own name is dropped before this, teaching.hear_lessons,
# fix round 2, residual 5).
PERSON_WORDS = frozenset({"i", "you", "we", "my", "your", "let", "me", "us", "our", "mine", "u", "he", "him", "she",
                          "her", "they", "them"})
# A word right after the subject that only exclaims or observes, not a claim ("cows look happy
# today", "cows rule!", "cow spotted near the lake", fix round 2, residual 6).
SKIP_WORDS = frozenset({"look", "looks", "seem", "seems", "rule", "rules", "rock", "rocks", "everywhere", "again",
                        "spotted"})
_RAW_WORD = re.compile(r"[a-z]+")
# A sentence boundary (., ! or ?) followed by space, but not inside a "..." pause (replies.clip's own
# pattern): a false or foreign word in one sentence never spoils a lesson a later one teaches cleanly.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?<!\.\.\.)\s+")


def number(n: int) -> str:
    return NUMBERS[n] if 0 <= n < len(NUMBERS) else str(n)


def gear_group(recipe: str) -> str:
    """ "tool", "weapon" or "armor" for an armor, tool or weapon recipe, else ""."""
    return next((group for group, endings in GROUPS if recipe.endswith(endings)), "")


def label(item: str) -> str:
    return "stick" if item == "sticks" else "plank" if item == "planks" else item.replace("_", " ")


def a(words: str) -> str:
    return f"{'an' if words[:1] in 'aeiou' else 'a'} {words}"


def amount(item: str, count: int) -> str:
    """ "two iron ingots", "a stick", "three string"."""
    words = label(item)
    if item in MASS:
        return f"{number(count)} {words}"
    return a(words) if count == 1 else f"{number(count)} {words}{'' if words.endswith('s') else 's'}"


def listed(parts: list[str]) -> str:
    return parts[0] if len(parts) == 1 else f"{', '.join(parts[:-1])} and {parts[-1]}"


def recipe_fact(name: str) -> str:
    """ "An iron sword takes two iron ingots and a stick, at a crafting table."; "A flint, a stick and
    a feather make four arrows, at a crafting table." """
    recipe = RECIPES[name]
    things = listed([amount(item, count) for item, count in recipe["ingredients"].items()])
    where = f", at {a(label(recipe['station']))}" if recipe.get("station") else ""
    made = recipe["output"].get(name, 1)
    if made > 1:
        return f"{things[:1].upper()}{things[1:]} make {number(made)} {label(name)}s{where}."
    subject = a(label(name))
    return f"{subject[:1].upper()}{subject[1:]} takes {things}{where}."


def teach_recipe(name: str) -> Lesson:
    """A recipe lesson for an armor, tool or weapon recipe (Part B's new recipes use it too)."""
    lesson = Lesson(f"recipe:{name}", "recipe", a(label(name)), recipe_fact(name))
    teach(lesson)
    return lesson


def plural(kind: str) -> str:
    return PLURAL.get(kind, kind.replace("_", " ") + "s")


def drop_words(item: str, drop) -> str:
    """ "one to three raw beef", "up to two leather", "sometimes a rabbit hide"."""
    if isinstance(drop, float):
        return f"sometimes {amount(item, 1)}"
    least, most = drop
    if least == most:
        return amount(item, least)
    if least == 0:
        return f"up to {amount(item, most)}"
    return f"{number(least)} to {amount(item, most)}"


def drops_fact(kind: Kind) -> str:
    name = a(kind.name.replace("_", " "))
    drops = listed([drop_words(item, drop) for item, drop in kind.drops.items()])
    return f"{name[:1].upper()}{name[1:]} drops {drops}."


def lands(biomes: tuple[str, ...]) -> str:
    """ "meadows, forests and swamps"; "every land" for a kind found in all of them."""
    if set(LANDS) <= set(biomes):
        return "every land"
    return listed([LANDS.get(biome, biome.replace("_", " ")) for biome in biomes])


def habits_fact(kind: Kind) -> str:
    if kind.name in HABITS:
        return HABITS[kind.name]
    many = plural(kind.name)
    least, most = kind.herd
    together = "alone" if most == 1 else f"{number(least)} to {number(most)} together"
    if kind.water:
        return f"{many[:1].upper()}{many[1:]} {WAYS.get(kind.name, 'swim')} in the water of every land, {together}."
    if kind.hostile:
        return f"{many[:1].upper()}{many[1:]} are dangerous: keep away from them."
    return f"{many[:1].upper()}{many[1:]} {WAYS.get(kind.name, 'roam')} in {lands(kind.biomes)}, {together}."


def teach_creatures() -> None:
    for kind in KINDS.values():
        words = a(kind.name.replace("_", " "))
        if kind.drops:
            teach(Lesson(f"{kind.name}:drops", "creature", words, drops_fact(kind)))
        teach(Lesson(f"{kind.name}:habits", "creature", words, habits_fact(kind)))


def teach_all() -> None:
    """Every recipe and creature lesson, from the tables as they are now."""
    for name in RECIPES:
        if gear_group(name):
            teach_recipe(name)
    teach_creatures()


# What the owner's words could teach --------------------------------------------------------------

def widened(word: str) -> set[str]:
    return set().union(*(group for group in TEACH_SYNONYMS if word in group)) | {word}


@dataclass(frozen=True)
class Keys:
    subjects: tuple[frozenset[str], ...]  # any one of these, all its words said, names what it is about
    words: frozenset[str]  # every word the lesson says or means


def tokens(text: str) -> list[str]:
    return words_of(text.replace("_", " ").replace(":", " "))


def named(lesson: Lesson) -> str:
    """What a lesson is about: "iron_sword" of "recipe:iron_sword", "cow" of "cow:drops"."""
    parts = lesson.thing.split(":")
    return parts[1] if parts[0] == "recipe" and len(parts) > 1 else parts[0]


def keys_of(lesson: Lesson) -> Keys:
    """A lesson's subjects (its thing's name and its words, their head word alone -- "coal" for coal
    ore, "mushroom" for a brown mushroom -- and, for a recipe, its material with its group: "iron
    armor"), each widened by TEACH_SYNONYMS, and every word it says or means."""
    thing, words = tokens(named(lesson)), tokens(lesson.words)
    group = gear_group(named(lesson)) if lesson.kind == "recipe" else ""
    subjects = {frozenset(thing), frozenset(words)}
    for found in (thing, words):
        if len(found) > 1:
            subjects.add(frozenset(found[:1] if found[-1] in ("ore", "mouth") else found[-1:]))
    if group:
        subjects.add(frozenset(thing[:-1] + [group]))
    for subject in list(subjects):
        for word in subject:
            for other in widened(word) - {word}:
                subjects.add(subject - {word} | {other})
    said = {*thing, *words, *tokens(lesson.fact), *([group] if group else [])}
    return Keys(tuple(sorted(subjects, key=sorted)), frozenset(set().union(*(widened(word) for word in said))))


_keys: tuple[int, dict[str, Keys], frozenset[str], frozenset[frozenset[str]]] | None = None


def lesson_keys() -> tuple[dict[str, Keys], frozenset[str], frozenset[frozenset[str]]]:
    """{thing: Keys} for every lesson, the world's words (things' names), and every lesson's own
    subject (so "iron" (iron_ore) + "sword" is seen as continuing into "iron sword"
    (recipe:iron_sword)'s own longer subject, not a claim about iron ore; fix round 2, residual 6),
    built again when a lesson is added."""
    global _keys
    if _keys is None or _keys[0] != len(LESSONS):
        keys = {thing: keys_of(lesson) for thing, lesson in LESSONS.items()}
        world = set(vocabulary()) | {word for found in keys.values() for subject in found.subjects for word in subject}
        all_subjects = frozenset(subject for found in keys.values() for subject in found.subjects)
        _keys = (len(LESSONS), keys, frozenset(world), all_subjects)
    return _keys[1], _keys[2], _keys[3]


@dataclass(frozen=True)
class Claims:
    taught: tuple[str, ...]  # the lessons the words fit, best first (at most SHORTLIST)
    doubtful: bool  # the words name what a lesson is about but say something no lesson says
    unknown: bool  # the words seem to teach about things no lesson is about


def asks(text: str) -> bool:
    first = next(iter(text.lower().split()), "")
    return text.rstrip().endswith("?") or first.strip(",.!") in QUESTION_WORDS


def raw_words(text: str) -> list[str]:
    """The lower-case, singular words of `text`, in order, stop words kept (for position checks)."""
    return [singular(word) for word in _RAW_WORD.findall(text.lower())]


def comma_after(text: str, width: int) -> bool:
    """A comma right after the first `width` words: an exclamation or address ("Skitters, yikes",
    "Chickens, chickens everywhere", fix round 2, residual 6)."""
    matches = list(_RAW_WORD.finditer(text.lower()))
    if len(matches) < width:
        return False
    return text[matches[width - 1].end():].lstrip().startswith(",")


def bare_claim(text: str, raw: list[str], subject: frozenset[str], found_words: frozenset[str],
              all_subjects: frozenset[frozenset[str]]) -> bool:
    """A short statement that starts by naming a known subject and is directly followed by a claim
    no lesson supports at all ("cows fly", doubtful even though "fly" is outside TEACH_VERBS): a
    copula right after the subject only describes it ("cows are cute", "cows are cute and
    friendly") unless a non-describing word follows too ("skitters are friendly and sing"); a word
    that only exclaims or observes ("cows look happy today", "cows rule!"), a comma right after the
    subject (an exclamation or address: "skitters, yikes"), or a word that only continues into
    another, longer known subject ("iron" (iron_ore) followed by "sword": "iron swords rock" is
    about recipe:iron_sword's subject, not a claim about iron ore) never is either; nor is talk of
    the owner (controller ruling, Task 6 review; fix round 2, residuals 5-7)."""
    if PERSON_WORDS & set(raw):
        return False
    width = len(subject)
    if set(raw[:width]) != subject:
        return False
    if comma_after(text, width):
        return False
    rest = raw[width:]
    if not rest or rest[0] in SKIP_WORDS or (subject | {rest[0]}) in all_subjects:
        return False
    copula = rest[0] in COPULA
    content = tokens(" ".join(rest[1:] if copula else rest))
    if not content or (copula and (len(content) <= 1 or set(content) <= DESCRIBING)):
        return False
    return bool(set(content) - found_words)


def claims_one(text: str) -> Claims:
    """`claims`, judged for one sentence alone."""
    if asks(text):
        return Claims((), False, False)
    keys, world, all_subjects = lesson_keys()
    said = set(tokens(text))
    things = said & world
    raw = raw_words(text)
    fits, doubtful = [], False
    for index, (thing, found) in enumerate(keys.items()):
        named = [subject for subject in found.subjects if subject <= said]
        if not named:
            continue
        subject = max(named, key=len)
        claim = (said & found.words) - subject
        foreign = things - found.words
        if foreign and (claim or said & TEACH_VERBS):
            doubtful = True
        elif claim:
            fits.append((-(len(claim) + len(subject)), index, thing))
        elif bare_claim(text, raw, subject, found.words, all_subjects):
            doubtful = True
    fits.sort()
    # Narrowed the way bare_claim narrows doubt (fix round 2, Important 2): no person words, and the
    # line must start with a recognized thing ("bread is made from wheat" stays unknown; "keep the
    # torch lit" does not, since "keep" is not a thing).
    unknown = (not fits and not doubtful and bool(things) and bool(said & TEACH_VERBS)
              and not (PERSON_WORDS & set(raw)) and bool(raw) and raw[0] in things)
    return Claims(tuple(thing for _, _, thing in fits[:SHORTLIST]), doubtful and not fits, unknown)


def claims(text: str) -> Claims:
    """What the owner's words could teach Mimo: only real lessons, never what they get wrong, each
    sentence judged on its own (`claims_one`), so a false or foreign word in one never spoils a
    lesson a later sentence teaches cleanly."""
    sentences = [sentence for sentence in SENTENCE_SPLIT.split(text.strip()) if sentence.strip()] or [text]
    if len(sentences) == 1:
        return claims_one(sentences[0])
    results = [claims_one(sentence) for sentence in sentences]
    taught: list[str] = []
    for result in results:
        taught.extend(thing for thing in result.taught if thing not in taught)
    doubtful = not taught and any(result.doubtful for result in results)
    unknown = not taught and not doubtful and any(result.unknown for result in results)
    return Claims(tuple(taught[:SHORTLIST]), doubtful, unknown)


teach_all()
