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

Words that fit a lesson but contradict it are `doubtful` too, never taught with a thank-you
(`contradicts`, the final fix wave): they deny it ("cows don't give leather", "cows never give
leather"), say a number the lesson does not ("a bow takes two sticks": it takes three) or say the
opposite of the lesson's own words ("skitters love sunlight": the sunlight makes them fade;
"skitters come out at noon": they come out at night).

Commands teach nothing (pre-flight 2, carry 5, the Mind follow-up's ruling): a sentence that opens
with one (COMMANDS: "make a bow!", "please wire up a lamp", "let's make a bow") teaches and doubts
nothing, and Bond B2's request question reads it instead (`wants`); a claim made only of verbs (VERBS)
teaches only as a statement about its subject ("coal burns"), never said before it ("you make a
bow"). A claim made only of numbers never teaches ("cows count in twos": two is only a detail of the
cow lessons). A verb of the claim whose clause says what, but no word the lesson knows, is doubtful
("cows give milk", "cows give milk and leather": no cow lesson speaks of milk; `unsupported`); a
describing word or an adverb there only says how ("cows give good leather", "coal burns well", Task 9
fix round 1), and any other word before the lesson's own is a claim of its own, doubtful too ("cows
give rotten beef", "sugar cane grows far from water", fix round 2). A copula followed by a word that
only observes
("cows are everywhere in this field") or after a modal ("sheep would be lovely") is chat, and a
lesson whose subject is only part of a longer one the words name ("iron" of "iron sword") never makes
them doubtful.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.services.crafting import RECIPES
from backend.survival.creatures.kinds import KINDS, Kind
from backend.survival.journal import LESSONS, Lesson, teach
from backend.survival.mind import singular, vocabulary, words_of
from backend.survival.wild import BY_NAME as SURVIVAL, KIND as SURVIVAL_KIND, PREFIX as SURVIVAL_PREFIX

SHORTLIST = 5  # lessons offered for one line
NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
GROUPS = (("tool", ("_pickaxe", "_axe")), ("weapon", ("_sword", "bow", "arrow")), ("armor", ("_cap", "_tunic")))
# Ingredients that are not counted one by one ("three string", "two leather").
MASS = frozenset({"string", "leather", "cobblestone", "raw_beef", "raw_mutton", "wool", "gloom_dust", "tallow",
                  "amber"})  # L5 (pre-flight): "two amber"
PLURAL = {"sheep": "sheep", "fish": "fish"}
LANDS = {"meadow": "meadows", "forest": "forests", "birch_forest": "birch forests", "taiga": "the taiga",
         "swamp": "swamps", "desert": "deserts", "alpine": "the mountains"}
# How the passive kinds live; a new kind without words here is described from its table alone.
WAYS = {"rabbit": "hop about", "chicken": "peck about", "sheep": "graze", "cow": "graze", "fish": "swim"}
# How the hostile kinds live (as backend.survival.creatures.hostiles has them).
HABITS = {
    "gloomling": "Gloomlings walk dark ground at night and the caves at any hour, and the sun burns them up.",
    "skitter": "Skitters live in the caves and dark places, and the sunlight makes them fade.",
    # L5 (pre-flight, carry 6): the thornback (backend.survival.creatures.thornback), so the owner can teach it.
    "thornback": "Thornbacks crawl the far wilds by day and by night; a sword glances off their shells, "
                 "but arrows hurt them.",
}
# Words that mean the same in the owner's mouth, both ways.
TEACH_SYNONYMS = (
    {"cap", "helmet", "hat"}, {"tunic", "shirt", "chestplate"}, {"pickaxe", "pick"}, {"sword", "blade"},
    {"cow", "cattle"}, {"skitter", "spider"}, {"gloomling", "zombie"}, {"rabbit", "bunny"},
    {"give", "drop"}, {"take", "need", "cost"}, {"make", "made", "craft"}, {"dark", "light", "shadow", "night"},
    {"sun", "sunlight", "day", "daylight", "light"}, {"fade", "burn"}, {"mountain", "alpine"},
    {"ingot", "bar"}, {"wooden", "wood"}, {"stone", "cobblestone"},
    # W1: the survival lessons' words (backend.survival.wild).
    {"purple", "dark", "night"}, {"herb", "sunleaf"}, {"bandage", "wrap"}, {"campfire", "fire"}, {"torch", "light"},
    {"shelter", "house", "home"}, {"poison", "poisonous", "toxic"}, {"cook", "cooked", "cooking"},
    {"festering", "fester"}, {"sickness", "sick", "ill"},
)
# Words every recipe lesson means, whether its fact says "takes" or "make" ("leather armor is made
# from leather", final fix wave M10).
RECIPE_WORDS = ("make", "made", "craft", "need", "take")
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
# What contradicts a lesson its words fit (`contradicts`, final fix wave I2): a word that denies it
# ("n't" is read as " not"), a number it does not say, or a word from the other side of one of
# OPPOSITES than the lesson's own words.
NEGATIONS = frozenset({"not", "no", "never", "nothing", "none", "without", "cannot", "dont", "doesnt", "didnt",
                       "cant", "wont", "isnt", "arent"})
COUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12}
OPPOSITES = ((frozenset({"love", "like", "enjoy"}), frozenset({"hate", "fear", "fade", "burn", "away", "avoid"})),
             (frozenset({"day", "daytime", "daylight", "noon", "morning", "sun", "sunlight", "sunny"}),
              frozenset({"night", "nighttime", "midnight", "dark", "evening"})),
             # W1: safe or poison, raw or cooked, kept away or brought, warm or cold (the survival lessons)
             (frozenset({"safe", "fine", "edible", "cure", "clean", "heal"}),
              frozenset({"poison", "poisonous", "toxic", "bad"})),
             (frozenset({"raw"}), frozenset({"cooked", "cook"})),
             (frozenset({"away"}), frozenset({"bring", "attract"})),
             (frozenset({"warm", "warmth"}), frozenset({"cold", "chill"})),
             # W2: harmless or dangerous (a storm, fog)
             (frozenset({"harmless", "safe"}), frozenset({"dangerous", "danger"})))
_NOT = ((re.compile(r"\bcan['’]t\b", re.IGNORECASE), "cannot"),
        (re.compile(r"\bwon['’]t\b", re.IGNORECASE), "will not"),
        (re.compile(r"n['’]t\b", re.IGNORECASE), " not"))
_DIGITS = re.compile(r"\d+")
_RAW_WORD = re.compile(r"[a-z]+")
# A sentence boundary (., ! or ?) followed by space, but not inside a "..." pause (replies.clip's own
# pattern): a false or foreign word in one sentence never spoils a lesson a later one teaches cleanly.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])(?<!\.\.\.)\s+")
# Pre-flight 2 (carry 5): the words a claim may hold that say nothing on their own: verbs (a teach verb,
# a recipe's own verbs and their synonyms) and numbers. `unsupported` passes over numbers and words of
# quantity to the word that says what.
VERBS = TEACH_VERBS | frozenset(RECIPE_WORDS) | frozenset({"cost"})
NUMBER_WORDS = frozenset(NUMBERS) | frozenset(COUNTS)
QUANTITY = frozenset({"plenty", "bunch", "couple", "pair", "load", "ton", "heap", "pile", "whole"})
# Task 9 fix round 1 (Important 1): the words `unsupported` passes over in a claim's clause besides
# numbers, quantities and talk of the owner, since they only say how or what kind ("cows give good
# leather", "coal burns well", "moss grows thick in forests", "lava burns things"): describing words,
# a small set of adverbs and words for things in general. Singular, as raw_words has them. Fix round 2
# (A): never a material ("golden", "wooden", "iron", "stone", "diamond"), a state ("rotten", "cooked")
# or a distance ("far", "away"): said before the lesson's own word, those are a claim of their own.
ADJECTIVES = DESCRIBING | frozenset({
    "good", "great", "tasty", "yummy", "delicious", "nice", "white", "strong", "shiny", "fine", "pretty", "beautiful",
    "warm", "fresh", "little", "best", "useful", "sturdy", "tough", "thin", "sharp", "heavy", "black", "grey",
    "gray", "real", "proper", "extra", "enough", "cool", "awesome", "amazing", "special", "perfect", "excellent",
    "juicy", "tender", "cozy", "fuzzy", "silky", "clean", "pure", "rich", "lot", "sticky", "smooth", "solid", "huge",
    "tiny", "large", "giant", "plain", "simple", "normal", "regular", "ordinary", "wonderful", "fantastic", "handy",
    "precious", "valuable", "pointy", "colorful", "colourful", "pale"})
ADVERBS = frozenset({
    "well", "brightly", "bright", "hot", "thick", "thickly", "near", "nearby", "next", "close", "quickly", "slowly",
    "easily", "easy", "always", "often", "usually", "mostly", "normally", "naturally", "quite", "super", "actually",
    "definitely", "probably", "totally", "apparently", "honestly", "certainly", "surely", "indeed", "still",
    "already", "anyway", "happily", "nicely", "gladly", "fully", "long", "strongly", "steadily", "tall", "high",
    "deep", "deeply", "right", "wild", "sure"})
GENERIC = frozenset({"thing", "stuff", "everything", "anything", "something", "item", "object", "material", "time"})
MEASURES = frozenset({"chunk", "piece", "bit", "slice", "lump", "bundle", "handful", "stack", "kind", "sort"})
# What ends a claim's clause for `unsupported`: a comma (or ";", ":", a dash) and these words; the end of
# the sentence and the next verb end it too.
CLAUSE_ENDS = frozenset({"and", "or", "but", "so", "because", "when", "while", "if", "then", "though", "although",
                         "unless", "until", "once", "whenever"})
_CLAUSE_PART = re.compile(r"[a-z]+|[,;:()]|\s[-–—]+\s")
MODALS = frozenset({"would", "will", "could", "should", "might", "must", "can", "may"})
# The words a command opens with (the first word of the sentence, singular): it asks for something, and
# teaches nothing.
COMMANDS = frozenset({"please", "go", "let", "make", "craft", "build", "find", "get", "dig", "fetch", "bring", "cook",
                      "smelt", "try", "visit", "explore", "wire", "put", "place", "plant", "hunt", "catch", "gather",
                      "collect", "chop", "grab"})


# W1: a warning teaches (resolution 8): a sentence that opens with "don't eat", "do not eat", "never eat" or
# "avoid", followed by what a poison lesson is about, reads as "<that> are poison"; followed by raw meat or
# fish, as "Cooked meat and fish are safe to eat." (`warned`). Its own "don't" would doubt a true warning.
WARNING = re.compile(r"^\s*(?:please\s+)?(?:(?:don['’]?t|do\s+not|never)\s+(?:ever\s+)?eat(?:ing)?|avoid(?:\s+eating)?)"
                     r"\s+(?:the\s+|any\s+)?(?P<rest>[^.!?]+?)[\s.!]*$", re.IGNORECASE)
RAW_MEAT = re.compile(r"^raw\s+(?:meat|fish|beef|mutton|chicken|rabbit)\b", re.IGNORECASE)
COOKED_IS_SAFE = "Cooked meat and fish are safe to eat."


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
    """ "one to three raw beef", "up to two leather", "sometimes a rabbit hide", "sometimes tallow"."""
    if isinstance(drop, float):
        return f"sometimes {label(item) if item in MASS else amount(item, 1)}"
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
    """What a lesson is about: "iron_sword" of "recipe:iron_sword", "cow" of "cow:drops", (W1) "fire" of
    "wild:fire"."""
    parts = lesson.thing.split(":")
    return parts[1] if parts[0] in ("recipe", "wild") and len(parts) > 1 else parts[0]


def keys_of(lesson: Lesson) -> Keys:
    """A lesson's subjects (its thing's name and its words, their head word alone -- "coal" for coal
    ore, "mushroom" for a brown mushroom -- and, for a recipe, its material with its group: "iron
    armor"), each widened by TEACH_SYNONYMS, and every word it says or means (a recipe's
    RECIPE_WORDS among them, whichever verb its fact uses)."""
    thing, words = tokens(named(lesson)), tokens(lesson.words)
    group = gear_group(named(lesson)) if lesson.kind == "recipe" else ""
    survival = SURVIVAL.get(named(lesson)) if lesson.kind == SURVIVAL_KIND else None
    subjects = {frozenset(thing), frozenset(words)}
    for found in (thing, words):
        if len(found) > 1:
            subjects.add(frozenset(found[:1] if found[-1] in ("ore", "mouth") else found[-1:]))
    if survival is not None:  # W1: a survival lesson names what it is about itself ("dark creatures", not "light")
        subjects = {frozenset(tokens(subject)) for subject in survival.subjects}
    if group:
        subjects.add(frozenset(thing[:-1] + [group]))
    for subject in list(subjects):
        for word in subject:
            for other in widened(word) - {word}:
                subjects.add(subject - {word} | {other})
    said = {*thing, *words, *tokens(lesson.fact), *([group] if group else []),
            *(RECIPE_WORDS if lesson.kind == "recipe" else ()), *(survival.means if survival is not None else ())}
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
    the owner (controller ruling, Task 6 review; fix round 2, residuals 5-7). A copula after a modal
    is a copula too ("sheep would be lovely"), and one followed by a word that only observes is no
    claim ("cows are everywhere in this field", pre-flight 2)."""
    if PERSON_WORDS & set(raw):
        return False
    width = len(subject)
    if set(raw[:width]) != subject:
        return False
    if comma_after(text, width):
        return False
    rest = raw[width:]
    if len(rest) > 1 and rest[0] in MODALS and rest[1] == "be":
        rest = ["is", *rest[2:]]
    if not rest or rest[0] in SKIP_WORDS or (subject | {rest[0]}) in all_subjects:
        return False
    copula = rest[0] in COPULA
    if copula and len(rest) > 1 and rest[1] in SKIP_WORDS:
        return False
    content = tokens(" ".join(rest[1:] if copula else rest))
    if not content or (copula and (len(content) <= 1 or set(content) <= DESCRIBING)):
        return False
    return bool(set(content) - found_words)


def denied(text: str) -> str:
    """`text` with its "n't" read as " not": "cows don't give leather" -> "cows do not give leather"."""
    for pattern, words in _NOT:
        text = pattern.sub(words, text)
    return text


def counts_in(text: str) -> set[int]:
    """The numbers `text` says, in words or digits ("a" is not one)."""
    return {int(digits) for digits in _DIGITS.findall(text)} | {
        COUNTS[word] for word in _RAW_WORD.findall(text.lower()) if word in COUNTS}


def contradicts(lesson: Lesson, text: str, raw: list[str]) -> bool:
    """Whether words that fit `lesson` contradict it: they deny it, say a number its fact does not,
    or say the opposite of its fact's own words ("love" of what the sunlight makes fade, "noon" of
    what comes out at night). A fact that says both sides ("the caves and dark places, and the
    sunlight") is never contradicted by either."""
    fact, words = set(raw_words(lesson.fact)), set(raw)
    if lesson.kind == SURVIVAL_KIND and named(lesson) in SURVIVAL:  # W1: what its fact stands for besides
        fact |= set(SURVIVAL[named(lesson)].sides)
    if words & NEGATIONS or counts_in(text) - counts_in(lesson.fact):
        return True
    return any((words & one and fact & other and not fact & one) or (words & other and fact & one and not fact & other)
               for one, other in OPPOSITES)


def clause_words(text: str) -> list[str]:
    """raw_words, with every clause break ("," ";" ":" a dash, and CLAUSE_ENDS: "and", "but" ...) as ","."""
    return ["," if part in CLAUSE_ENDS or not part[:1].isalpha() else singular(part)
            for part in _CLAUSE_PART.findall(f" {text.lower()} ")]


def unsupported(marked: list[str], claim: frozenset[str], words: frozenset[str]) -> bool:
    """A verb of the claim whose clause says what, but not what the lesson knows ("cows give milk":
    what cows give, and no cow lesson speaks of milk; pre-flight 2, carry 5). Task 9 fix round 1: the
    clause runs from the verb to the next clause break (`clause_words`: a comma, "and" ...), the end of
    the sentence or the next verb, and a lesson word in it is enough ("sugar cane grows near water", "a
    bow needs strong string"). Stop words, talk of the owner, numbers (`contradicts` checks those),
    words of quantity, describing words, a few adverbs and words for things in general say only how or
    what kind, and are passed over: a clause of nothing else says nothing more, like a verb at the end
    ("coal burns", "coal burns well", "lava burns things"). "cows give milk and leather" is still
    doubted: its first clause holds only milk. Fix round 2 (A): any other word before the clause's
    first lesson word is a claim the lesson does not make, and doubted ("sugar cane grows far from
    water", "an iron sword needs golden ingots", "cows give rotten beef"). A claim that holds none of the
    sentence's verbs (a lesson that says "digs" where the owner says "need") is read from the sentence's
    own verbs instead ("diamonds need a golden pickaxe")."""
    passed = PERSON_WORDS | NUMBER_WORDS | QUANTITY | MEASURES | ADJECTIVES | ADVERBS | GENERIC
    verbs = ([place for place, word in enumerate(marked) if word in claim and word in VERBS]
             or [place for place, word in enumerate(marked) if word in VERBS])
    for place in verbs:
        for later in marked[place + 1:]:
            if later == "," or later in VERBS or later in COPULA:
                break
            content = tokens(later)
            if not content:
                continue
            if content[0] in words:
                break
            if later not in passed:
                return True
    return False


def warned(text: str) -> str:
    """W1: a warning said as the fact it warns of ("Don't eat the purple berries." -> "purple berries are
    poison."; "Never eat raw meat." -> COOKED_IS_SAFE), or the words as they are."""
    match = WARNING.match(text)
    if match is None:
        return text
    rest = match.group("rest").strip()
    if RAW_MEAT.match(rest):
        return COOKED_IS_SAFE
    keys, _, _ = lesson_keys()
    said = set(tokens(rest))
    for name, lesson in SURVIVAL.items():
        found = keys.get(f"{SURVIVAL_PREFIX}{name}")
        if found is not None and "poison" in raw_words(lesson.fact) and any(subject <= said for subject in found.subjects):
            return f"{rest} are poison."
    return text


def commanded(text: str) -> bool:
    """A sentence that opens with a command ("make a bow!", "please wire up a lamp", "let's go"):
    it asks for something and teaches nothing (pre-flight 2, carry 5)."""
    raw = raw_words(text)
    return bool(raw) and raw[0] in COMMANDS


def wants(text: str) -> bool:
    """Whether any sentence of the owner's words asks a question or opens with a command: what Bond
    B2's request question reads, even beside a sentence that teaches (pre-flight 2, carry 5)."""
    sentences = [sentence for sentence in SENTENCE_SPLIT.split(text.strip()) if sentence.strip()] or [text]
    return any(asks(sentence) or commanded(sentence) for sentence in sentences)


def teaches(raw: list[str], subject: frozenset[str], claim: frozenset[str]) -> bool:
    """Whether a claim that fits a lesson teaches it (pre-flight 2, carry 5): it says something besides
    verbs and numbers ("cows give leather"), or it is made only of verbs said after what it is about, a
    statement ("coal burns"). Said before its subject, a claim made only of verbs is a command or a wish
    ("make a bow!", "craft an iron sword"), and one made only of numbers says nothing ("cows count in
    twos": two is only a detail of the cow lessons)."""
    if claim - VERBS - NUMBER_WORDS:
        return True
    verbs = [place for place, word in enumerate(raw) if word in claim and word in VERBS]
    named = [place for place, word in enumerate(raw) if word in subject]
    return bool(verbs) and bool(named) and min(named) < min(verbs)


def claims_one(text: str) -> Claims:
    """`claims`, judged for one sentence alone. Pre-flight 2 (carry 5): a command teaches and doubts
    nothing (`commanded`); a claim teaches only when `teaches` says so (not one made only of verbs said
    before its subject, nor bare numbers); a verb followed by a word the lesson does not know is
    doubtful (`unsupported`); and a lesson whose subject is only part of a longer one the words name
    ("iron" of "iron sword") never makes them doubtful: the words are about the longer one, which
    decides ("you should craft an iron sword" is no doubtful claim about iron ore). W1: a warning is read as
    the fact it warns of (`warned`), and a command still teaches a survival lesson whose words it fits with
    nothing wrong ("Cook your meat on a fire."), doubting nothing (resolution 8)."""
    text = warned(text)
    commanding = commanded(text)
    if asks(text):
        return Claims((), False, False)
    keys, world, all_subjects = lesson_keys()
    text = denied(text)
    said = set(tokens(text))
    things = said & world
    raw = raw_words(text)
    marked = clause_words(text)
    matched = {}
    for index, (thing, found) in enumerate(keys.items()):
        if commanding and LESSONS[thing].kind != SURVIVAL_KIND:
            continue
        named = [subject for subject in found.subjects if subject <= said]
        if named:
            matched[thing] = (index, found, max(named, key=len))
    subjects = {subject for _, _, subject in matched.values()}
    fits, doubtful = [], False
    for thing, (index, found, subject) in matched.items():
        inside = any(subject < other for other in subjects)
        claim = (said & found.words) - subject
        foreign = things - found.words
        if (foreign and (claim or said & TEACH_VERBS)) or (
                claim and (contradicts(LESSONS[thing], text, raw) or unsupported(marked, claim, found.words))):
            doubtful = doubtful or not inside
        elif claim and teaches(raw, subject, claim):
            fits.append((-(len(claim) + len(subject)), index, thing))
        elif not inside and bare_claim(text, raw, subject, found.words, all_subjects):
            doubtful = True
    fits.sort()
    if commanding:
        return Claims(tuple(thing for _, _, thing in fits[:SHORTLIST]), False, False)
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
