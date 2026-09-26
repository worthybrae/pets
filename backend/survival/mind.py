"""Mimo's memory (Mind M1, docs/superpowers/specs/2026-09-26-mind-and-making-design.md): one stream.

Every notable experience is a row of the world's mind_memories:
- at (server time) and game_day (the clock's day number when it happened);
- kind: "episode" (something that happened), "gist" (a game day summed up at night), "thought" (a
  reflection), "told" (something the owner taught) or "lesson" (something Mimo learned itself);
- text: written by rules in Mimo's voice, at most TEXT_LIMIT characters, never by a model;
- about: tags (creature kinds, blocks, items, places, biomes, goals, "owner"), at most TAGS_KEPT,
  kept in mind_tags too so recall finds them by index;
- importance from 1 to 10 and feeling from -2 to 2, set by the rules for each kind of moment;
- strength: 1 at first and one more each time the memory is recalled (up to STRENGTH_TOP), with
  last_recalled;
- source: what wrote it (an event kind, "gist", an insight) and count: how many moments it stands
  for (a merged episode: "I caught 9 fish.").

Recall (`recall`) is pure rules and never calls a model. Each candidate scores recency +
importance + relevance: recency, from 1 down, halves every HALF_LIFE game days times the memory's
strength, so a rehearsed memory fades slower; importance is importance / 10; relevance is how much
of the cue the memory covers, from 0 to 1 and counted RELEVANCE_WEIGHT times, so what the cue asks
about comes first: each word of the cue is looked for among the memory's tags (a thing's name,
worth TAG_WEIGHT) or its words, itself counting whole and through SYNONYMS half (cow: cattle, beef,
leather; armor: cap, tunic, iron; a moment's verb in its other forms, VERB_FORMS: hunting, hunted). The candidates come from indexed pre-filters, never a scan of
the stream: the newest memories tagged with the cue's tags (TAGGED), the newest (RECENT) and the
most important (IMPORTANT), at most POOL in all. Recalling only reads:
`rehearse` writes the strength, and only write paths call it (a chat reply that quotes a memory, a
goal choice that was shown a thought); a GET never does.

The stream holds at most CAP items. A write that takes it past CAP forgets down to CAP - ROOM
(`enforce_cap`): the least important first and, among equals, the weakest (the lowest
`keep_score`, importance x strength against age), so every moment that mattered outlives the small
ones. Gists and thoughts are never forgotten while anything else is left; only a life so long that
its gists alone fill the stream (thousands of game days) loses its oldest gists. A world from before
Mind gains the tables the first time it is opened for writing; one only ever read (an archive)
remembers nothing.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from backend.survival.bond_tables import missing_table
from backend.survival.clock import DAY_SECONDS

KINDS = ("episode", "gist", "thought", "told", "lesson")
KEPT = ("gist", "thought")  # never forgotten while anything else can go
TEXT_LIMIT = 160
TAGS_KEPT = 8
CAP = 5000  # items in one life's stream
ROOM = 50  # past CAP, forget down to CAP - ROOM, so forgetting is not every write
HALF_LIFE = 2.0  # game days
STRENGTH_TOP = 8.0
FADE = 3.0  # game days: keep_score's scale for age
TAG_WEIGHT = 2
RELEVANCE_WEIGHT = 3.0
POOL = 400  # candidates recall scores at most
TAGGED, RECENT, IMPORTANT = 200, 150, 50
SHOWN = {"recent": 8, "moments": 6, "thoughts": 6, "days": 14}  # /api/mimo's memories
MOMENT = 6  # importance from which a memory is a moment that mattered
MEMORY_COLUMNS = ("id", "at", "game_day", "kind", "text", "about", "importance", "feeling", "strength",
                  "last_recalled", "source", "count")
STOPWORDS = frozenset(
    "a an the and or but if then so of to in on at by for from with without about into onto over under up down out "
    "off is are was were be been being am do does did done have has had having i me my mine myself you your yours "
    "we us our they them their it its itself he him his she her hers this that these those there here what which "
    "who whom whose when where why how all any some no not nor only own same too very just can could should would "
    "will shall may might must also again ever never now once more most much many such than other each few both "
    "every lot lots really oh hey hi hello ok okay yes yeah please thanks thank remember recall tell story know "
    "think".split())
PLACES = frozenset({"home", "house", "cave", "lake", "water", "river", "camp", "pit", "shelter", "farm", "pen", "hill",
                    "mountain", "night", "dark", "day", "expedition", "trip", "food", "owner", "snack", "bandage",
                    "armor", "tool", "weapon", "animal", "creature", "monster", "ore", "light", "sun"})
# Parts of names too plain to be a tag on their own ("first" of first_shelter, "raw" of raw_beef).
PLAIN = frozenset({"better", "cooked", "dead", "far", "first", "full", "new", "raw", "safe", "tall", "polished",
                   "mossy", "ripe", "leave", "block", "panel", "hull", "solar", "brown", "red", "orange", "pink",
                   "yellow", "map", "path", "tile", "roof", "land",
                   # Making final fix wave (I5): thinking_machine, cozy_home and the lit parts (lamp_lit ...)
                   "thinking", "cozy", "lit",
                   # Making wave 2 (the re-review's Minor 4): pressure_plate and iron_bars
                   "pressure", "bar"})
# The cue's words widened (the spec's cow -> cattle, beef, leather; armor -> cap, tunic, iron).
SYNONYMS: dict[str, tuple[str, ...]] = {
    "cow": ("cattle", "beef", "leather"), "cattle": ("cow", "beef"), "beef": ("cow",),
    "leather": ("cow", "rabbit", "hide", "cap", "tunic"), "hide": ("rabbit", "leather"),
    "armor": ("cap", "tunic", "iron", "leather"), "armour": ("armor", "cap", "tunic", "iron", "leather"),
    "helmet": ("cap",), "hat": ("cap",), "shirt": ("tunic",), "chestplate": ("tunic",),
    "sheep": ("wool", "mutton"), "wool": ("sheep",), "mutton": ("sheep",), "chicken": ("feather", "egg"),
    "feather": ("chicken", "arrow"), "bunny": ("rabbit",), "rabbit": ("hide",), "fish": ("fishing", "lake"),
    "fishing": ("fish", "lake"), "spider": ("skitter",), "skitter": ("string", "cave"), "zombie": ("gloomling",),
    "monster": ("gloomling", "skitter"), "gloomling": ("gloom", "dark"), "tool": ("pickaxe", "axe"),
    "weapon": ("sword", "bow", "arrow"), "pick": ("pickaxe",), "mine": ("ore", "pickaxe"), "dig": ("pickaxe",),
    "house": ("home",), "home": ("house", "shelter"), "trip": ("expedition",), "journey": ("expedition", "trip"),
    "adventure": ("expedition", "trip"), "night": ("dark", "sleep"), "dark": ("night",), "scary": ("hurt", "danger"),
    "food": ("ate", "meal", "hunt", "fish"), "eat": ("ate", "meal", "food"), "hungry": ("hunger", "food"),
    "mountain": ("alpine",), "hill": ("alpine",), "lake": ("water", "fish"), "gift": ("snack", "owner"),
}
# A moment's verb in its other forms (the final fix wave's M9): "do you remember hunting?" brings
# back "I hunted a cow.", since recall only reduces plurals. With what such a moment says besides
# (VERB_ALSO: exploring finds things, eating is a meal); each form widens to the others.
VERB_FORMS = (("hunt", "hunted", "hunting"), ("camp", "camped", "camping"), ("fight", "fought", "fighting"),
              ("explore", "explored", "exploring"), ("eat", "ate", "eating"), ("craft", "crafted", "crafting"),
              ("build", "built", "building"), ("sleep", "slept", "sleeping"))
VERB_ALSO = {"explore": ("found",), "eat": ("meal",)}
for _forms in VERB_FORMS:
    for _form in _forms:
        SYNONYMS[_form] = tuple(dict.fromkeys([*SYNONYMS.get(_form, ()), *(other for other in _forms if other != _form),
                                               *VERB_ALSO.get(_forms[0], ())]))
SINGULARS = {"zombies": "zombie", "cookies": "cookie", "pies": "pie", "lies": "lie", "movies": "movie"}
_WORD = re.compile(r"[a-z]+")
_vocabulary: tuple[tuple, frozenset[str]] | None = None


def singular(word: str) -> str:
    """ "cows" -> "cow", "berries" -> "berry", "torches" -> "torch"; "grass" and "cactus" stay."""
    if word in SINGULARS:
        return SINGULARS[word]
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def words_of(text: str) -> list[str]:
    """The content words of `text`, lower case and singular, in order."""
    return [singular(word) for word in _WORD.findall(str(text).lower()) if word not in STOPWORDS]


def vocabulary() -> frozenset[str]:
    """Every name of a thing in Mimo's world and its parts, for tags: blocks, items, recipes,
    creatures and what they drop, biomes, places and goals. Built again when a registry grew."""
    global _vocabulary
    from backend.services.crafting import BLOCKS, RECIPES, SMELTING
    from backend.survival.creatures.kinds import KINDS as CREATURES
    from backend.survival.goals import GOALS
    key = (len(BLOCKS), len(RECIPES), len(CREATURES), len(GOALS))
    if _vocabulary is not None and _vocabulary[0] == key:
        return _vocabulary[1]
    names = set(BLOCKS) | set(RECIPES) | set(SMELTING) | set(SMELTING.values()) | set(CREATURES) | set(GOALS)
    for recipe in RECIPES.values():
        names |= set(recipe["ingredients"]) | set(recipe["output"])
    for kind in CREATURES.values():
        names |= set(kind.drops) | set(kind.biomes)
    found = set(PLACES)
    for name in names:
        found.add(singular(name))
        found.update(singular(part) for part in name.split("_") if part.isalpha() and len(part) > 2
                     and singular(part) not in PLAIN)
    _vocabulary = (key, frozenset(found))
    return _vocabulary[1]


def tags_in(text: str) -> list[str]:
    """The things `text` is about, in order: each word or pair of words that names something in
    Mimo's world ("iron ore" gives iron_ore, iron and ore)."""
    known, words, found = vocabulary(), words_of(text), []
    for index, word in enumerate(words):
        pair = f"{word}_{words[index + 1]}" if index + 1 < len(words) else ""
        for tag in (pair, word):
            if tag and tag in known and tag not in found:
                found.append(tag)
    return found


@dataclass(frozen=True)
class Cue:
    """What a recall looks for: each word of the cue with its synonyms, and whether it names a thing."""
    terms: tuple[tuple[str, frozenset[str], bool], ...]

    @property
    def tags(self) -> frozenset[str]:
        known = vocabulary()
        return frozenset(word for _, words, _ in self.terms for word in words if word in known)


def cue_of(text: str, about: tuple[str, ...] = ()) -> Cue:
    known, terms = vocabulary(), []
    for word in dict.fromkeys([*about, *words_of(text)]):
        words = frozenset({word, *SYNONYMS.get(word, ())})
        terms.append((word, words, bool(words & known)))
    return Cue(tuple(terms))


@dataclass(frozen=True)
class Memory:
    id: int
    at: float
    game_day: int
    kind: str
    text: str
    about: tuple[str, ...]
    importance: int
    feeling: int
    strength: float
    last_recalled: float | None
    source: str
    count: int


@dataclass(frozen=True)
class Recalled:
    memory: Memory
    score: float
    recency: float
    relevance: float


def memory_of(row) -> Memory:
    values = dict(zip(MEMORY_COLUMNS, tuple(row)))
    values["about"] = tuple(values["about"].split()) if values["about"] else ()
    return Memory(**values)


def create_mind_tables(db: sqlite3.Connection) -> None:
    """The memory stream's tables. Run inside the caller's BEGIN IMMEDIATE; again changes nothing."""
    db.execute("CREATE TABLE IF NOT EXISTS mind_memories (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, "
               "game_day INTEGER NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL, about TEXT NOT NULL DEFAULT '', "
               "importance INTEGER NOT NULL, feeling INTEGER NOT NULL DEFAULT 0, strength REAL NOT NULL DEFAULT 1, "
               "last_recalled REAL, source TEXT NOT NULL DEFAULT '', count INTEGER NOT NULL DEFAULT 1)")
    db.execute("CREATE INDEX IF NOT EXISTS mind_by_kind ON mind_memories(kind, id)")
    db.execute("CREATE INDEX IF NOT EXISTS mind_by_kind_importance ON mind_memories(kind, importance, id)")
    db.execute("CREATE INDEX IF NOT EXISTS mind_by_importance ON mind_memories(importance, id)")
    db.execute("CREATE INDEX IF NOT EXISTS mind_by_day ON mind_memories(game_day, kind)")
    db.execute("CREATE TABLE IF NOT EXISTS mind_tags (tag TEXT NOT NULL, memory INTEGER NOT NULL, "
               "PRIMARY KEY (tag, memory)) WITHOUT ROWID")
    db.execute("CREATE INDEX IF NOT EXISTS mind_tags_by_memory ON mind_tags(memory)")


def mind_state(state: dict) -> dict:
    """What the mind keeps in the state (state["mind"]), with the fields an older state lacks: the
    last game day consolidated, the day's tally of events, when Mimo last reflected, its nudges, and
    whether its memory has gone back to the first event."""
    mind = state.setdefault("mind", {})
    for key, value in (("day", 0), ("tally", {"day": 0, "kinds": {}}), ("reflected", 0), ("rules_thought", 0),
                       ("nudges", {}), ("near_death", 0), ("started", False)):
        mind.setdefault(key, value)
    return mind


def trimmed(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT - 3].rstrip() + "..."


def clamp(value: float, low: int, high: int) -> int:
    return int(max(low, min(high, round(value))))


def add_memory(db: sqlite3.Connection, at: float, game_day: int, kind: str, text: str, about=(), importance: int = 3,
               feeling: int = 0, source: str = "", count: int = 1, strength: float = 1.0) -> int:
    """Remember something. Tags are the ones given, then the things the text names. Returns its id."""
    if kind not in KINDS:
        raise ValueError(f"no memory kind {kind!r}")
    text = trimmed(text)
    tags = list(dict.fromkeys([*about, *tags_in(text)]))[:TAGS_KEPT]
    memory = db.execute("INSERT INTO mind_memories(at, game_day, kind, text, about, importance, feeling, strength, "
                        "source, count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (at, game_day, kind, text, " ".join(tags), clamp(importance, 1, 10), clamp(feeling, -2, 2),
                         min(STRENGTH_TOP, max(1.0, strength)), source, max(1, count))).lastrowid
    db.executemany("INSERT OR IGNORE INTO mind_tags(tag, memory) VALUES (?, ?)", [(tag, memory) for tag in tags])
    enforce_cap(db, game_day)
    return memory


def forget(db: sqlite3.Connection, ids) -> None:
    ids = list(ids)
    for start in range(0, len(ids), 500):
        chunk = ids[start:start + 500]
        marks = ",".join("?" * len(chunk))
        db.execute(f"DELETE FROM mind_tags WHERE memory IN ({marks})", chunk)
        db.execute(f"DELETE FROM mind_memories WHERE id IN ({marks})", chunk)


# importance x strength against age: FADE game days halve it, three FADEs quarter it.
KEEP_SCORE = "importance * strength * ? / (? + MAX(0, ? - game_day))"


def keep_score(memory: Memory, today: int) -> float:
    return memory.importance * memory.strength * FADE / (FADE + max(0, today - memory.game_day))


def forget_weakest(db: sqlite3.Connection, today: int, how_many: int) -> int:
    """Forget `how_many` memories: the least important first and, among equals, the lowest
    keep_score, the oldest first on a tie; gists and thoughts only when nothing else is left, and
    then the oldest gists."""
    if how_many <= 0:
        return 0
    marks = ",".join("?" * len(KEPT))
    ids = [row[0] for row in db.execute(
        f"SELECT id FROM mind_memories WHERE kind NOT IN ({marks}) ORDER BY importance, {KEEP_SCORE}, id LIMIT ?",
        (*KEPT, FADE, FADE, today, how_many)).fetchall()]
    if len(ids) < how_many:  # KEPT[0], the gists, go before the thoughts
        ids += [row[0] for row in db.execute("SELECT id FROM mind_memories WHERE kind=? ORDER BY id LIMIT ?",
                                             (KEPT[0], how_many - len(ids))).fetchall()]
    forget(db, ids)
    return len(ids)


def count_memories(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM mind_memories").fetchone()[0]


def enforce_cap(db: sqlite3.Connection, today: int, cap: int | None = None) -> int:
    """Past the cap, forget the weakest down to CAP - ROOM. Returns how many were forgotten."""
    cap = CAP if cap is None else cap
    count = count_memories(db)
    return forget_weakest(db, today, count - (cap - ROOM)) if count > cap else 0


# Recall ---------------------------------------------------------------------------------------

def candidates(db: sqlite3.Connection, cue: Cue, kinds: tuple[str, ...] | None = None) -> list[int]:
    """The ids recall scores, from the indexes only: the newest tagged with the cue's tags, the
    newest and the most important, at most POOL."""
    ids: list[int] = []
    tags = sorted(cue.tags)
    if tags:
        marks = ",".join("?" * len(tags))
        ids += [row[0] for row in db.execute(f"SELECT DISTINCT memory FROM mind_tags WHERE tag IN ({marks}) "
                                             "ORDER BY memory DESC LIMIT ?", (*tags, TAGGED)).fetchall()]
    if kinds is None:
        ids += [row[0] for row in db.execute("SELECT id FROM mind_memories ORDER BY id DESC LIMIT ?", (RECENT,))]
        ids += [row[0] for row in db.execute("SELECT id FROM mind_memories ORDER BY importance DESC, id DESC LIMIT ?",
                                             (IMPORTANT,))]
    else:
        share = max(1, len(kinds))
        for kind in kinds:
            ids += [row[0] for row in db.execute("SELECT id FROM mind_memories WHERE kind=? ORDER BY id DESC LIMIT ?",
                                                 (kind, -(-RECENT // share)))]
            ids += [row[0] for row in db.execute("SELECT id FROM mind_memories WHERE kind=? "
                                                 "ORDER BY importance DESC, id DESC LIMIT ?",
                                                 (kind, -(-IMPORTANT // share)))]
    return list(dict.fromkeys(ids))[:POOL]


def recency_of(memory: Memory, now: float, scale: float) -> float:
    days = max(0.0, now - memory.at) * scale / DAY_SECONDS
    return 0.5 ** (days / (HALF_LIFE * min(STRENGTH_TOP, max(1.0, memory.strength))))


def relevance_of(memory: Memory, cue: Cue) -> float:
    """How much of the cue the memory covers, from 0 to 1: a word that names a thing counts
    TAG_WEIGHT and is looked for among the memory's tags, any other word among its words; found
    itself it counts whole, found only through a synonym half."""
    if not cue.terms:
        return 0.0
    tags, words = set(memory.about), set(words_of(memory.text)) | set(memory.about)
    whole = found = 0.0
    for word, options, thing in cue.terms:
        weight, among = (TAG_WEIGHT, tags) if thing else (1, words)
        whole += weight
        found += weight if word in among else weight / 2 if options & among else 0.0
    return found / whole


def recall(db: sqlite3.Connection, cue: str | Cue, now: float, scale: float, limit: int = 5,
           kinds: tuple[str, ...] | None = None) -> list[Recalled]:
    """The memories that come to mind for `cue` (words, or a Cue), best first: recency + importance +
    relevance over the pre-filtered candidates. Reads only. A world without the tables has none."""
    cue = cue if isinstance(cue, Cue) else cue_of(cue)
    try:
        ids = candidates(db, cue, kinds)
        if not ids:
            return []
        marks = ",".join("?" * len(ids))
        rows = db.execute(f"SELECT {','.join(MEMORY_COLUMNS)} FROM mind_memories WHERE id IN ({marks})", ids).fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return []
    found = []
    for row in rows:
        memory = memory_of(row)
        if kinds is not None and memory.kind not in kinds:
            continue
        recency, relevance = recency_of(memory, now, scale), relevance_of(memory, cue)
        score = recency + memory.importance / 10 + RELEVANCE_WEIGHT * relevance
        found.append(Recalled(memory, score, recency, relevance))
    found.sort(key=lambda item: (-item.score, -item.memory.id))
    return found[:limit]


def rehearse(db: sqlite3.Connection, ids, now: float) -> None:
    """Recalling strengthens: each memory's strength grows by one (up to STRENGTH_TOP). Write paths only."""
    ids = list(dict.fromkeys(ids))
    if ids:
        marks = ",".join("?" * len(ids))
        db.execute(f"UPDATE mind_memories SET strength = MIN(?, strength + 1), last_recalled = ? WHERE id IN ({marks})",
                   (STRENGTH_TOP, now, *ids))


# What /api/mimo shows ---------------------------------------------------------------------------

def item_of(memory: Memory) -> dict:
    return {"id": memory.id, "at": memory.at, "day": memory.game_day, "kind": memory.kind, "text": memory.text,
            "importance": memory.importance, "feeling": memory.feeling}


def memories_view(db: sqlite3.Connection) -> dict:
    """The memories for /api/mimo: how many there are, the newest few things that happened, the
    moments that mattered most, the newest thoughts and the newest days' gists (newest first each).
    A world from before Mind remembers nothing. Reads only."""
    columns = ",".join(MEMORY_COLUMNS)

    def rows(where: str, order: str, limit: int) -> list[dict]:
        found = db.execute(f"SELECT {columns} FROM mind_memories WHERE {where} ORDER BY {order} LIMIT ?", (limit,))
        return [item_of(memory_of(row)) for row in found.fetchall()]

    try:
        return {
            "count": count_memories(db),
            "recent": rows("kind IN ('episode', 'told', 'lesson')", "id DESC", SHOWN["recent"]),
            "moments": rows(f"kind IN ('episode', 'told') AND importance >= {MOMENT}", "importance DESC, id DESC",
                            SHOWN["moments"]),
            "thoughts": rows("kind = 'thought'", "id DESC", SHOWN["thoughts"]),
            "days": rows("kind = 'gist'", "id DESC", SHOWN["days"]),
        }
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return {"count": 0, "recent": [], "moments": [], "thoughts": [], "days": []}


def mind_fields(world, now: float, scale: float) -> dict:
    """What /api/mimo shows of Mimo's memory while it lives, read in a read-only transaction of its own."""
    with world.connect() as db:
        db.execute("BEGIN")
        return {"memories": memories_view(db)}


# What may reach Luna -----------------------------------------------------------------------------

STORY_KINDS = ("episode", "lesson", "gist", "thought")  # never "told": it holds the owner's words
PRIVATE = "owner"  # the tag of a memory about the owner


def story_memories(db: sqlite3.Connection, day: int, limit: int = 5) -> list[Memory]:
    """A game day's top memories, the most important first, for a story a model tells (Bond B3's
    daily story, on Luna). Never a told memory, which holds the owner's words, nor one about the
    owner: only the owner's name may reach Luna. Reads only."""
    columns, marks = ",".join(MEMORY_COLUMNS), ",".join("?" * len(STORY_KINDS))
    try:
        rows = db.execute(f"SELECT {columns} FROM mind_memories WHERE game_day=? AND kind IN ({marks}) AND id NOT IN "
                          "(SELECT memory FROM mind_tags WHERE tag=?) ORDER BY importance DESC, id DESC LIMIT ?",
                          (day, *STORY_KINDS, PRIVATE, limit)).fetchall()
    except sqlite3.OperationalError as error:
        if not missing_table(error):
            raise
        return []
    return [memory_of(row) for row in rows]


# The memorial (Mind M3) --------------------------------------------------------------------------

MEMORIAL_GISTS = 400  # the newest gists a memorial lists: more than a year of game days


def life_memories(world) -> dict:
    """A life's memories for its memorial: the newest MEMORIAL_GISTS gists and every thought (a
    thought is kept once and strengthened when had again, so there are few), each oldest first. A
    world from before Mind remembers nothing."""
    columns = ",".join(MEMORY_COLUMNS)
    with world.connect() as db:
        try:
            gists = db.execute(f"SELECT {columns} FROM mind_memories WHERE kind='gist' ORDER BY id DESC LIMIT ?",
                               (MEMORIAL_GISTS,)).fetchall()
            thoughts = db.execute(f"SELECT {columns} FROM mind_memories WHERE kind='thought' ORDER BY game_day, id"
                                  ).fetchall()
        except sqlite3.OperationalError as error:
            if not missing_table(error):
                raise
            return {"gists": [], "thoughts": []}
    return {"gists": [item_of(memory_of(row)) for row in reversed(gists)],
            "thoughts": [item_of(memory_of(row)) for row in thoughts]}
