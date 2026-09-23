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
_RENDER_KEYS = {"name", "textures", "layer", "solid", "replaceable"}

# Gameplay properties keyed by name, in the shape crafting.BLOCKS has always had.
BLOCK_PROPERTIES: dict[str, dict] = {
    block["name"]: {key: value for key, value in block.items() if key not in _RENDER_KEYS}
    for block in BLOCK_LIST if block["name"] != "air"
}


def is_replaceable(material: str) -> bool:
    """True for cells a placed or falling block may take over: air, water and plants."""
    index = BLOCK_IDS.get(material)
    return index is not None and bool(BLOCK_LIST[index].get("replaceable"))
