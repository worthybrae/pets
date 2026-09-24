"""Block registry shared with the viewer.

shared/blocks.json is the single list of blocks. The viewer turns each entry into a
texture and a numeric id (its index); the server uses the same names and properties.
"""

from __future__ import annotations

import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).resolve().parents[2] / "shared" / "blocks.json"
_REGISTRY = json.loads(REGISTRY_PATH.read_text())

TILES: dict[str, dict] = _REGISTRY["tiles"]
BLOCK_LIST: list[dict] = _REGISTRY["blocks"]
BLOCK_IDS: dict[str, int] = {block["name"]: index for index, block in enumerate(BLOCK_LIST)}
_RENDER_KEYS = {"name", "textures", "layer", "solid", "replaceable", "shape"}

# Gameplay properties keyed by name, in the shape crafting.BLOCKS has always had.
BLOCK_PROPERTIES: dict[str, dict] = {
    block["name"]: {key: value for key, value in block.items() if key not in _RENDER_KEYS}
    for block in BLOCK_LIST if block["name"] != "air"
}


def is_replaceable(material: str) -> bool:
    """True for cells a placed or falling block may take over: air, water and plants."""
    index = BLOCK_IDS.get(material)
    return index is not None and bool(BLOCK_LIST[index].get("replaceable"))


def is_plant(material: str) -> bool:
    """True for natural decorations with the cutout layer: tall grass and flowers."""
    index = BLOCK_IDS.get(material)
    return index is not None and BLOCK_LIST[index].get("layer") == "cutout"


TALL = frozenset(block["name"] for block in BLOCK_LIST if block.get("tall"))


def is_tall(material: str) -> bool:
    """True for blocks too tall to stand on or step over (the registry's `tall`: fences, L3)."""
    return material in TALL


def is_solid(material: str) -> bool:
    """True for blocks Mimo can stand on or shelter under (the registry's `solid`)."""
    index = BLOCK_IDS.get(material)
    return index is not None and bool(BLOCK_LIST[index].get("solid"))


def hardness(material: str) -> float | None:
    """Seconds to mine the block by hand (registry `hardness`), or None when it cannot be mined."""
    index = BLOCK_IDS.get(material)
    if index is None:
        return None
    seconds = BLOCK_LIST[index].get("hardness")
    return None if seconds is None else float(seconds)


def mining_tool(material: str) -> str | None:
    """The tool that speeds up mining the block (registry `tool`): "pickaxe", "axe" or None."""
    index = BLOCK_IDS.get(material)
    return None if index is None else BLOCK_LIST[index].get("tool")
