"""W1: what a wild pet eats, and what eating does to it ("Hazards" 1 and 2 of the Wild World spec).

A wild newborn eats its familiar foods by instinct (wild.FAMILIAR: apples, carrots, bread, brown mushrooms,
fish and meat). Red berries and red mushrooms are untried: it picks and carries them, but eats one only as a
taste, one serving a meal, when it must: hunger under TASTE_BELOW with no familiar or known-safe food carried
and nothing holding it back (HOLDS: a question it asked and is waiting on, backend.survival.questions), or at
once when starving (the eat_now reflex, under 15). Until it knows `wild:nightberries` the two red berries are
one group to it: a meal of red berries eats from what it carries in proportion to the counts, a seeded roll a
serving (`wild_meal`). Once it knows `wild:berries` it eats the group freely (nightberries too, until it learns
them apart). A pet that knows `wild:cooking` eats raw meat and fish only when starving. Sunleaf is medicine,
never a meal (backend.survival.ailments).

Eating, for a wild pet (steps.EATING: `eat_wild`):
- a nightberry or a red mushroom takes 5 health at once (never the last point) and gives a tummy ache: "Pip ate
  nightberries and felt sick.";
- a meal that holds raw food rolls once, on its first raw serving, at the highest chance among its raw items
  (RAW_RISK: raw chicken 0.5; beef, mutton and rabbit 0.35; fish 0.2): a tummy ache on a hit;
- a sickness from the red berries makes Mimo shun the whole group for wild.SHUN (2 game days): "Berries made
  me sick. I'll leave them alone for a while." (backend.survival.knocks lifts it when the sickness taught it
  the difference);
- spoiled food (backend.survival.spoilage) fills 4 hunger and gives a tummy ache with chance SPOILED_RISK, and
  is eaten only when hungry with nothing else to eat, by a pet that does not know `wild:keeping`.
A food that made Mimo sick is not eaten again in that meal: the rest of its servings (of the whole group, for the
red berries) are dropped from the queue. The step is marked with what happened (`sick`, `raw`) for what learns
from it after (the knocks).
`throw_out` (58, a need) drops what Mimo knows is poison once it carries any, and spoiled food once it knows
`wild:keeping`.

A gentle pet keeps today's rules (purposes.meal, steps.FOOD_HEALTH and FOOD_RISK): MEALS and EATING give it
nothing, and it only ever avoids nightberries (wild.avoided).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.services.crafting import take_items
from backend.survival.ailments import fall_sick, lose
from backend.survival.goals import add_urge
from backend.survival.nature import roll
from backend.survival.once import log_once
from backend.survival.purposes import FULL, MEALS, Purpose, register
from backend.survival.situation import Situation
from backend.survival.spoilage import SPOILED
from backend.survival.steps import EATING, FOOD, HERBS, label
from backend.survival.wild import FAMILIAR, RED_BERRIES, RED_MUSHROOM, is_wild, knows, wild_state

if TYPE_CHECKING:
    from backend.survival.actions import ActionContext

logger = logging.getLogger(__name__)

TASTE_BELOW = 50.0  # hunger under which an untried food is tasted, when nothing else is carried
STARVING = 15.0  # reflexes.EAT_NOW_BELOW: starving, it tastes at once
POISON_HEALTH = 5.0
POISONOUS = ("nightberries", RED_MUSHROOM)  # what makes a wild pet sick for sure
RAW_RISK = {"raw_chicken": 0.5, "raw_beef": 0.35, "raw_mutton": 0.35, "raw_rabbit": 0.35, "raw_fish": 0.2}
SHARE_CHANNEL = 203  # the red berries' share roll
RAW_CHANNEL = 201  # a raw meal's roll
SPOILED_CHANNEL = 202
SPOILED_RISK = 0.6
SHUN_WORDS = "Berries made me sick. I'll leave them alone for a while."
# W1: functions (Situation, item) that hold a taste of an untried food back (a question Mimo is waiting on:
# backend.survival.questions). One that crashes holds nothing back (logged once).
HOLDS: list = []


def pet_cell(state: dict) -> tuple[int, int, int]:
    position = state["position"]
    return round(position["x"]), round(position["y"]), round(position["z"])


def grouped(s: Situation) -> bool:
    """The two red berries are one food to Mimo: it does not know nightberries yet."""
    return not knows(s, "nightberries")


def untried(s: Situation, item: str) -> bool:
    """A food Mimo has to try before it trusts it."""
    if item in RED_BERRIES:
        return not knows(s, "berries")
    return item == RED_MUSHROOM and not knows(s, "red_mushroom")


def held(s: Situation, item: str) -> bool:
    """Something holds a taste of `item` back (HOLDS)."""
    for holds in HOLDS:
        try:
            if holds(s, item):
                return True
        except Exception as error:
            log_once(logger, "taste held", error)
    return False


def trusted(s: Situation, item: str) -> bool:
    """A food Mimo eats as a meal: familiar, or one it learned is safe (the red berries once it knows them)."""
    return item in FAMILIAR or (item in RED_BERRIES and not untried(s, item))


def may_taste(s: Situation, item: str, eatable: list[str]) -> bool:
    """Mimo tastes an untried food now: starving, or hungry with nothing it trusts to eat and nothing holding
    it back."""
    hunger = s.vitals["hunger"]
    if hunger < STARVING:
        return True
    return hunger < TASTE_BELOW and not any(trusted(s, food) for food in eatable) and not held(s, item)


def share(s: Situation, counts: dict[str, int], serving: int) -> str:
    """Which red berry a serving of the group is: nightberries at their share of the two (a seeded roll)."""
    total = counts.get("berries", 0) + counts.get("nightberries", 0)
    chance = counts.get("nightberries", 0) / total if total else 0.0
    picked = roll(s.seed, pet_cell(s.state), SHARE_CHANNEL, int(s.at) + serving) < chance
    return "nightberries" if picked else "berries"


def wild_meal(s: Situation, full: float = FULL) -> list[dict] | None:
    """purposes.MEALS: a wild pet's meal, best first, until hunger would reach `full` (None for a gentle pet:
    purposes.meal). An untried food is a single taste, the red berries a group while Mimo cannot tell them
    apart, raw food only while Mimo does not know to cook it (or is starving); the meal's first raw serving
    carries the meal's risk."""
    if not is_wild(s.state):
        return None
    hunger = s.vitals["hunger"]
    starving = hunger < STARVING
    cooks = knows(s, "cooking") and not starving
    counts = {item: count for item, count in s.inventory.items()
              if count > 0 and item in FOOD and item not in s.poisons and item not in HERBS and item != SPOILED
              and not (cooks and item in RAW_RISK)}
    if not counts and s.inventory.get(SPOILED, 0) > 0 and hunger < TASTE_BELOW and not knows(s, "keeping"):
        counts = {SPOILED: s.inventory[SPOILED]}  # nothing else left: what went bad
    eatable = sorted(counts, key=lambda item: (untried(s, item), -FOOD[item], item))  # what it trusts first
    steps: list[dict] = []
    served = 0
    together = grouped(s) and all(item in counts for item in RED_BERRIES)
    for item in eatable:
        if together and item == "nightberries":
            continue  # eaten with the berries, as one food
        tasting = untried(s, item)
        if tasting and not may_taste(s, item, eatable):
            continue
        servings = 1 if tasting else counts[item] + (counts.get("nightberries", 0) if together and item == "berries" else 0)
        while servings > 0 and hunger < full:
            eaten = share(s, counts, served) if together and item == "berries" else item
            counts[eaten] -= 1
            steps.append({"kind": "eat", "item": eaten})
            servings -= 1
            served += 1
            hunger += FOOD[eaten]
    risk = max((RAW_RISK[step["item"]] for step in steps if step["item"] in RAW_RISK), default=0.0)
    first_raw = next((step for step in steps if step["item"] in RAW_RISK), None)
    if first_raw is not None:
        first_raw["risk"] = risk
    return steps


MEALS.append(wild_meal)


# Eating ------------------------------------------------------------------------------------------

def eat_raw_left(state: dict, item: str, at: float) -> tuple[str, str] | None:
    """carrying.eat_what_is_left: a starving wild pet ate raw food it had no room to carry, on the spot. The raw
    meal's roll, once (RAW_RISK, RAW_CHANNEL); the sickness's event, or None."""
    if roll(state.get("world_seed", "0"), pet_cell(state), RAW_CHANNEL, int(at)) < RAW_RISK.get(item, 0.0):
        return sick_from(state, item, at)
    return None


def sick_from(state: dict, item: str, at: float) -> tuple[str, str]:
    """Mimo ate `item` and it made it sick: a tummy ache, the rest of that food left uneaten this meal, and the red
    berries shunned for a while."""
    fall_sick(state, "tummy", at)
    same = RED_BERRIES if item in RED_BERRIES else (item,)
    if state.get("queue"):
        state["queue"] = [spec for spec in state["queue"] if not (spec.get("kind") == "eat" and spec.get("item") in same)]
    if item in RED_BERRIES:
        wild_state(state)["shun"]["red_berries"] = at
        state["last_thought"] = SHUN_WORDS
    return "sick", f"{state['name']} ate {label(item)} and felt sick."


def eat_wild(step: dict, state: dict, at: float) -> tuple[str, str] | None:
    """steps.EATING: a wild pet's eat step (None for a gentle pet's and for an herb's)."""
    item = step["item"]
    if not is_wild(state) or item in HERBS or item not in FOOD:
        return None
    vitals = state["vitals"]
    state["inventory"] = take_items(state["inventory"], {item: 1})
    vitals["hunger"] = min(100.0, vitals["hunger"] + FOOD[item])
    if item in POISONOUS:
        before = vitals["health"]
        vitals["health"] = max(min(before, 1.0), before - POISON_HEALTH)
        lose(state, before - vitals["health"])  # lost to a hazard (backend.survival.ailments)
        step["sick"] = True
        return sick_from(state, item, at)
    if item == SPOILED:
        if roll(state.get("world_seed", "0"), pet_cell(state), SPOILED_CHANNEL, int(at)) < SPOILED_RISK:
            step["sick"] = True
            return sick_from(state, item, at)
        return "ate", f"{state['name']} ate {label(item)}."
    risk = float(step.get("risk", 0.0))
    if risk > 0:
        step["raw"] = True
        if roll(state.get("world_seed", "0"), pet_cell(state), RAW_CHANNEL, int(at)) < risk:
            step["sick"] = True
            return sick_from(state, item, at)
    return "ate", f"{state['name']} ate {label(item)}."


EATING.append(eat_wild)


# throw_out ---------------------------------------------------------------------------------------

def junk_food(s: Situation) -> list[tuple[str, int]]:
    """(item, count) Mimo carries and knows it must not eat: poison it learned (nightberries, red mushrooms), and
    food that went bad once it knows keeping."""
    known = (("nightberries", "nightberries"), (RED_MUSHROOM, "red_mushroom"), (SPOILED, "keeping"))
    return [(item, s.inventory[item]) for item, lesson in known if s.inventory.get(item, 0) > 0 and knows(s, lesson)]


def throw_out_valid(s: Situation) -> bool:
    return is_wild(s.state) and bool(junk_food(s))


def plan_throw_out(s: Situation, context: ActionContext) -> list[dict]:
    if s.brain["batches"] > 0:
        return []
    return [{"kind": "drop", "item": item, "amount": count} for item, count in junk_food(s)]


add_urge("throw_out", throw_out_valid)
register(Purpose(
    "throw_out", "throw out what is bad", "Drop food it knows is poison, so it is never eaten by mistake.",
    valid=throw_out_valid,
    facts=lambda s: "carrying " + ", ".join(f"{count} {label(item)}" for item, count in junk_food(s)),
    score=lambda s: 58.0, plan=plan_throw_out,
    thoughts=("I'm not eating those. Out they go.", "Better get rid of the bad stuff.")))
