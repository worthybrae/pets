"""Bond's final fix wave, T2 (I1): every event text the game writes, through every surface that puts
it in Mimo's mouth, reads in Mimo's own voice.

The templates are built from the game's own tables: every goal's title and milestones, its day plan and
step sentences, every lesson fact, every creature kind, every biome's words, the words a trip finds,
every structure's name (shelters, stone houses, the farm, the pen, the workshop and each machine, which
carry the pet's name) and the event log's other shapes. Each goes through the inbox's writers (a report,
a discovery, danger, a seed hatching), the story's highlights (one day and a long absence), the chat's
news line, Mind's memory and its gist clause, and the words of a request's answer. None may say the
pet's name, call Mimo "it", or put a third-person verb after "I".
"""

import random
import re
import tempfile
import unittest
from pathlib import Path

import backend.survival.brain  # noqa: F401  (every goal, machine and lesson registered)
from backend.survival import bonding, minding  # noqa: F401  (every writer registers)
from backend.survival.blueprints import NAMES, NOUNS
from backend.survival.building import FINISHED_WORDS
from backend.survival.consolidation import clause
from backend.survival.creatures.kinds import KINDS
from backend.survival.curiosity import BIOME_WORDS
from backend.survival.diary import absence_highlights, day_highlights
from backend.survival.episodes import moment_of, moment_text
from backend.survival.events import MIRRORS
from backend.survival.goals import GOALS, lower, plan_sentence, step_sentence
from backend.survival.hatch import hatch
from backend.survival.inbox import CONSUMER
from backend.survival.lessons import teach_all
from backend.survival.machines import MACHINES, title_of
from backend.survival.purposes import PURPOSES
from backend.survival.registry import LifeRegistry
from backend.survival.replies import Heard, in_my_voice, news
from backend.survival.requests import lapse_words, note_for, to_do
from backend.survival.situation import from_db
from backend.survival.steps import label
from backend.survival.world import SurvivalWorld, log_event, read_state

BORN = 1_000_000.0
SCALE = 60.0
NAME = "Clover"
# "it" that is a thing, never Mimo: a spot made home, a blow made it through, a cave's walls, a site for
# the bigger home, the chest the food goes in, and what
# an event says in brackets (a goal's or a purpose's reason) or quotes (Mimo's own thought).
THING_ITS = ("made it home", "made it through", "in its walls", "(it kept failing)", "(it cannot be done now)",
             "(nothing to do for it now)", '"It is time to go."', "a site for it", "food in it",
             "worked it out")  # W1: what Mimo worked out itself
IT = re.compile(r"\b(?:it|its|itself)\b")
PET = re.compile(rf"\b{NAME}\b")
# A third-person verb where Mimo speaks as "I": "I is", "I am stuck ... and starts digging out".
THIRD_PERSON = re.compile(r"\bI (?:is|has|does|knows|needs|wants|starts|digs|gets|goes|makes|keeps|comes|sees|"
                          r"carries)\b|\b(?:I|am)\b[^.!?\"]*\band (?:starts|digs|gets|goes|makes|has|is|keeps|comes)\b")


def templates() -> list[tuple[str, str]]:
    """(event kind, text) for every event text the game can write about Mimo."""
    found = []
    for goal in GOALS.values():
        title = lower(goal.title)
        found += [("goal", f"{NAME} reached a goal: {title}."),
                  ("plan", f'{NAME} set a new goal: {title}. "I want this."'),
                  ("plan", plan_sentence(NAME, [{"text": milestone.text} for milestone in goal.milestones[:3]])),
                  ("plan", f'{NAME} set a new goal: {title}. "It is time to go."'),
                  ("plan", f"{NAME} set a goal aside for now: {title} (no progress for a day)."),
                  ("plan", f"{NAME} set a goal aside for now: {title} (it cannot be done now)."),
                  ("plan", f"{NAME} set a goal aside for now: {title} (nothing to do for it now).")]
        for milestone in goal.milestones:
            found += [("plan", step_sentence(NAME, goal, milestone)),
                      ("plan", plan_sentence(NAME, [{"text": milestone.text}]))]
    for purpose in PURPOSES.values():
        found.append(("plan", f"{NAME} gave up trying to {purpose.phrase} (it kept failing)."))
    teach_all()
    from backend.survival.journal import LESSONS
    for lesson in LESSONS.values():
        found.append(("learned", f"{NAME} learned that {lesson.fact[:1].lower()}{lesson.fact[1:]}"))
    for kind in KINDS.values():
        words = label(kind.name)
        found += [("found", f"{NAME} met its first {words}."), ("hurt", f"{NAME} was hit by a {kind.name}."),
                  ("threat", f"{NAME} saw a {kind.name.replace('_', ' ')} coming."),
                  ("fight", f"{NAME} fought off a {words}."), ("hunt", f"{NAME} hunted a {words}."),
                  ("ate", f"{NAME} ate raw {words}."), ("ate", f"{NAME} ate 2 raw {words} it had no room to carry.")]
    for words in BIOME_WORDS.values():
        found += [("found", f"{NAME} saw {words} for the first time."), ("found", f"{NAME} found {words}.")]
    for words in ("water it did not know", "birch trees", "a cave mouth with iron ore and coal ore in its walls",
                  "a sinkhole with iron ore in its walls", "flat ground for a bigger home", "a cow to hunt",
                  "a creature seed", "water with fish", "wild berries", "something new"):
        found.append(("found", f"{NAME} found {words}."))
    names = {f"{NAME}'s {roof} {noun}" for roof in NAMES.values() for noun in (*NOUNS.values(), "Hut")}
    names |= {f"{NAME}'s {roof} Stone House" for roof in NAMES.values()}
    names |= {f"{NAME}'s farm", f"{NAME}'s pen", f"{NAME}'s Workshop"}
    names |= {title_of(machine, NAME) for machine in MACHINES.values()}
    for what in sorted(names):
        found.append(("built", f"{NAME} finished building {what} and moved in."))
        for kind in ("farm", "pen", *FINISHED_WORDS):
            words = FINISHED_WORDS.get(kind, "{name} laid out {what}.")
            found.append(("built", words.format(name=NAME, what=what)))
    found += [("discovered", f"{NAME} found water."),
              ("discovered", f"{NAME} found a sheltered spot and made it home."),
              ("found", f"{NAME} spotted iron ore."), ("trapped", f"{NAME} is stuck in a pit and starts digging out."),
              ("starving", f"{NAME} is starving."), ("freezing", f"{NAME} is freezing."),
              ("hungry", f"{NAME} is getting hungry."), ("fall", f"{NAME} fell 4 blocks and got hurt."),
              ("computer", f"{NAME} built a machine that remembers how long it has been alive!"),
              ("expedition", f"{NAME} set out on an expedition to the north."),
              ("expedition", f"{NAME} came home from its expedition: 248 blocks out, 2 nights camped, "
                             "3 new things learned."),
              ("camp", f"{NAME} dug in for the night and made a camp."),
              ("birth", f"{NAME} hatched into a brand-new world."), ("hello", f"You said hello to {NAME}."),
              ("care", f"You gave {NAME} a snack."), ("care", f"You bandaged {NAME}."),
              ("owner", f"You crafted iron pickaxe for {NAME}."), ("fish", f"{NAME} caught a fish."),
              ("grow", "A creature seed grew into a sheep."), ("ate", f"{NAME} ate cooked beef."),
              ("sick", f"{NAME} ate rotten flesh and felt sick.")]
    # L5 (pre-flight, carry 6): the rings, the ruins, their old chests and the manual one may hold.
    from backend.survival.rings import RINGS
    from backend.survival.ruins import LOOT, loot_words
    for _, ring, _ in RINGS:
        found += [("found", f"{NAME} reached the {ring.lower()} for the first time."),
                  ("found", f"{NAME} found an old ruin in the {ring.lower()}.")]
    for table in LOOT.values():
        found.append(("loot", f"{NAME} opened an old chest in a ruin: "
                              f"{loot_words({item: most for item, _, most, _ in table})}."))
    found += [("loot", f"{NAME} opened an old chest in a ruin: {loot_words({})}."),
              ("found", f"{NAME} found an old manual in the ruin's chest.")]
    # W1: a wild pet's sicknesses, wounds, food gone bad, nights, what it worked out and what it asked.
    from backend.survival.wild import SURVIVAL
    from backend.survival.wonders import WONDERS
    found += [("cured", f"{NAME} ate sunleaf and felt better."), ("wound", f"A skitter cut {NAME}."),
              ("festering", f"{NAME}'s wound is festering."), ("dressed", f"{NAME} wrapped its wound in a bandage."),
              ("dressed", f"{NAME} pressed sunleaf on its wound."), ("spoiled", f"{NAME}'s raw beef went bad."),
              ("chill", f"{NAME} caught a chill in the night."), ("sick", f"{NAME} ate nightberries and felt sick."),
              ("sick", f"{NAME} ate raw chicken and felt sick."), ("sick", f"{NAME} ate spoiled food and felt sick."),
              ("rested", f"{NAME} slept soundly in its bed."), ("safe_night", f"{NAME} spent a quiet night at home.")]
    found += [("figured", f"{NAME} worked out that {lesson.figured}.") for lesson in SURVIVAL]
    found += [("asked", f"{NAME} asked you {wonder.asked}.") for wonder in WONDERS.values()]
    return list(dict.fromkeys(found))


class VoiceTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        root = Path(cls.directory.name)
        registry = LifeRegistry(root / "data", root / "no-legacy.sqlite3")
        life = hatch(registry, random.Random(8), timestamp=BORN)
        cls.world = SurvivalWorld(registry.world_path(life))
        cls.name = life["name"]  # the templates are written for NAME, then said of this pet
        cls.templates = [(kind, text.replace(NAME, cls.name)) for kind, text in templates()]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def leaks(self, surface: str, raw: str, said: str | None, fact: str = "") -> list[str]:
        """What is wrong with `said`, the words a surface made of the event `raw`."""
        if not said:
            return []
        wrong = []
        rest = said.replace(fact.rstrip(".!?"), "") if fact else said
        for allowed in THING_ITS:
            rest = rest.replace(allowed, "")
        if re.search(rf"\b{self.name}\b", said):
            wrong.append("the pet's name")
        if IT.search(rest):
            wrong.append(f"'{IT.search(rest).group(0)}' for Mimo")
        if THIRD_PERSON.search(said):
            wrong.append(f"a third-person verb: '{THIRD_PERSON.search(said).group(0)}'")
        return [f"[{surface}] {raw!r} -> {said!r}: {', '.join(wrong)}"] if wrong else []

    def test_every_event_text_reads_in_mimos_voice_on_every_surface(self):
        name, problems = self.name, []
        state = {"name": name, "brain": {}, "born_at": BORN}
        writers = {kind: entry.write for kind, entries in MIRRORS.items() for entry in entries
                   if entry.consumer == CONSUMER}
        for number, (kind, raw) in enumerate(self.templates):
            event = {"id": number + 1, "at": BORN + 1, "kind": kind, "text": raw, "day": 1}
            fact = ""
            if kind == "learned":
                fact = raw.split(" learned that ", 1)[1]
                self.assertEqual(in_my_voice(raw, name), f"I learned that {fact}")  # a lesson's own "it"s stay
            problems += self.leaks("voice", raw, in_my_voice(raw, name), fact)
            if kind in writers:  # the inbox
                with self.world.transaction() as db:
                    live = read_state(db)
                    live.setdefault("bond", {}).pop("danger_at", None)
                    newest = db.execute("SELECT COALESCE(MAX(id), 0) FROM mimo_inbox").fetchone()[0]
                    writers[kind](db, live, event, BORN + 1, SCALE)
                    row = db.execute("SELECT text FROM mimo_inbox WHERE id > ? ORDER BY id DESC LIMIT 1",
                                     (newest,)).fetchone()
                problems += self.leaks("inbox", raw, row[0] if row else None)
            for what, text in day_highlights([event], state):  # the story, one day
                problems += self.leaks(f"story:{what}", raw, text, fact)
            for text in absence_highlights([event, {**event, "id": 0, "day": 2}], state, 1, 2):  # a long absence
                problems += self.leaks("story:days", raw, text, fact)
            if moment_of(event, name) is not None:  # Mind's memory and its gist
                memory = moment_text(event, name)
                problems += self.leaks("memory", raw, memory, fact)
                gist = clause(memory)
                problems += self.leaks("gist", raw, gist, fact)
                if gist.startswith(("am ", "is ")):
                    problems.append(f"[gist] {raw!r} -> {gist!r}: a gist clause in the present tense")
        self.assertEqual(problems, [], "\n".join(problems[:60]))

    def test_the_chats_news_line_voices_the_newest_notable_event(self):
        problems = []
        for kind, raw in self.templates:
            if kind in ("plan", "learned", "hunt", "fight", "hurt", "threat", "ate", "fish", "hello", "owner", "grow"):
                continue  # routine: never news
            with self.world.transaction() as db:
                log_event(db, BORN + 5, kind, raw)
                state = read_state(db)
                line = news(from_db(db, state, BORN + 6, SCALE), Heard("any news?"))
            problems += self.leaks("news", raw, line)
        self.assertEqual(problems, [], "\n".join(problems[:60]))

    def test_a_requests_answers_name_every_goal_in_mimos_voice(self):
        problems = []
        for goal in GOALS.values():
            for said in (note_for(None, goal, "reached", 50.0, 0.0)["answer"], to_do(goal), lapse_words(goal, False),
                         lapse_words(goal, True)):
                problems += self.leaks("request", goal.title, said)
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
