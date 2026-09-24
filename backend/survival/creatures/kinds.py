"""The kinds of creature, as a registry of plain data (spec L1, "Creatures table and registry").

A Kind says how much health a creature has, how fast it walks (`speed`, seconds per block; it
flees at double speed), how big it is (`size`, blocks tall, for the viewer), whether it is
`hostile`, how much `damage` its attack does and from how far (`reach`), what it drops when it
dies (`drops`: item -> (least, most), or item -> the chance of one), the biomes it spawns in, how
many come together (`herd`), whether it lives in `water` (fish) and whether it runs off when hurt
(`flee_when_hurt`). L1 registers the passive rabbit, chicken, sheep and cow, and fish; L2's
hostile kinds register themselves the same way, with `hostile`, `damage` and `reach` set.
"""

from __future__ import annotations

from dataclasses import dataclass, field

Drop = tuple[int, int] | float  # (least, most) of the item, or the chance of exactly one


@dataclass(frozen=True)
class Kind:
    name: str
    health: float
    speed: float  # seconds per block while walking; fleeing takes half as long
    size: float  # blocks tall
    hostile: bool = False
    damage: float = 0.0  # what one attack of its own does to Mimo (L2)
    reach: float = 0.0  # how close it must be to attack (L2)
    drops: dict[str, Drop] = field(default_factory=dict)
    biomes: tuple[str, ...] = ()  # where herds spawn; a water kind spawns in any biome's water
    herd: tuple[int, int] = (1, 1)  # how many spawn together, least and most
    water: bool = False  # lives in water (fish), else on land and never in water
    flee_when_hurt: bool = True


KINDS: dict[str, Kind] = {}


def register_kind(kind: Kind) -> Kind:
    """Add a kind, or replace the one with the same name."""
    KINDS[kind.name] = kind
    return kind


def kind_of(name) -> Kind | None:
    """The registered kind called `name`, or None."""
    return KINDS.get(name) if isinstance(name, str) else None


def land_kinds(biome: str) -> list[Kind]:
    """The passive land kinds whose herds spawn in `biome`, in registration order."""
    return [kind for kind in KINDS.values() if not kind.water and not kind.hostile and biome in kind.biomes]


def water_kinds() -> list[Kind]:
    return [kind for kind in KINDS.values() if kind.water and not kind.hostile]


def huntable(kind: Kind | None) -> bool:
    """Mimo hunts passive land animals: not fish, and (from L2) not the hostile kinds it fights."""
    return kind is not None and not kind.water and not kind.hostile


register_kind(Kind("rabbit", health=3.0, speed=0.35, size=0.5, drops={"raw_rabbit": (1, 1), "rabbit_hide": 0.5},
                   biomes=("meadow", "forest", "desert", "alpine"), herd=(1, 3)))
register_kind(Kind("chicken", health=4.0, speed=0.6, size=0.6, drops={"raw_chicken": (1, 1), "feather": (0, 2)},
                   biomes=("meadow", "forest"), herd=(2, 4)))
register_kind(Kind("sheep", health=8.0, speed=0.7, size=1.0, drops={"raw_mutton": (1, 2), "wool": (1, 2)},
                   biomes=("meadow", "alpine"), herd=(2, 4)))
register_kind(Kind("cow", health=10.0, speed=0.8, size=1.3, drops={"raw_beef": (1, 3), "leather": (0, 2)},
                   biomes=("meadow", "forest"), herd=(2, 3)))
register_kind(Kind("fish", health=2.0, speed=0.8, size=0.3, herd=(2, 4), water=True))
