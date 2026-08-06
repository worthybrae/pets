"""Tool executor for pet brain actions."""

import json
import logging
import math
import random
import re
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import httpx

from backend.models.memory import RawEvent
from backend.services.food import deduct_food
from backend.services.memory import MemoryService
from backend.services.events import get_broadcaster
from backend.services.world import WorldService, save_pet_body, save_pet_position

logger = logging.getLogger(__name__)

# In-memory stores (will be replaced with DB later)
_pet_positions: dict[str, dict[str, float]] = {}
_pet_agendas: dict[str, list[dict]] = {}
_pet_knowledge: dict[str, dict[str, str]] = {}
_raw_events: list[RawEvent] = []


# ---- OpenAI Tool Schemas ----

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "place_voxels",
            "description": "Place voxels in the world. Each voxel has a position and RGBA color.",
            "parameters": {
                "type": "object",
                "properties": {
                    "voxels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "z": {"type": "integer"},
                                "r": {"type": "integer", "minimum": 0, "maximum": 255},
                                "g": {"type": "integer", "minimum": 0, "maximum": 255},
                                "b": {"type": "integer", "minimum": 0, "maximum": 255},
                                "a": {"type": "integer", "minimum": 0, "maximum": 255},
                            },
                            "required": ["x", "y", "z", "r", "g", "b", "a"],
                        },
                        "maxItems": 5000,
                        "description": "Array of voxels to place (max 5000). For larger builds use fill_region, place_sphere, or place_cylinder.",
                    }
                },
                "required": ["voxels"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fill_region",
            "description": "Fill a rectangular region with voxels. Generates up to 200,000 voxels server-side. Use for walls, floors, platforms, terrain, large structures. Supports color gradients and random noise for natural-looking surfaces.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer", "description": "Start X (inclusive)"},
                    "y1": {"type": "integer", "description": "Start Y (inclusive)"},
                    "z1": {"type": "integer", "description": "Start Z (inclusive)"},
                    "x2": {"type": "integer", "description": "End X (inclusive)"},
                    "y2": {"type": "integer", "description": "End Y (inclusive)"},
                    "z2": {"type": "integer", "description": "End Z (inclusive)"},
                    "r": {"type": "integer", "minimum": 0, "maximum": 255},
                    "g": {"type": "integer", "minimum": 0, "maximum": 255},
                    "b": {"type": "integer", "minimum": 0, "maximum": 255},
                    "a": {"type": "integer", "minimum": 0, "maximum": 255, "description": "Alpha (default 255)"},
                    "noise": {"type": "integer", "minimum": 0, "maximum": 60, "description": "Random RGB variation per voxel (0=solid, 30=natural stone, 60=very noisy)"},
                    "hollow": {"type": "boolean", "description": "If true, only place the outer shell (1 voxel thick walls)"},
                    "gradient_color": {
                        "type": "object",
                        "properties": {
                            "r": {"type": "integer"}, "g": {"type": "integer"}, "b": {"type": "integer"},
                        },
                        "description": "If set, color blends from (r,g,b) at bottom to this color at top",
                    },
                },
                "required": ["x1", "y1", "z1", "x2", "y2", "z2", "r", "g", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_sphere",
            "description": "Place a sphere of voxels. Generates up to 200,000 voxels server-side. Great for domes, boulders, orbs, planets, organic shapes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cx": {"type": "integer", "description": "Center X"},
                    "cy": {"type": "integer", "description": "Center Y"},
                    "cz": {"type": "integer", "description": "Center Z"},
                    "radius": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Radius in voxels"},
                    "r": {"type": "integer", "minimum": 0, "maximum": 255},
                    "g": {"type": "integer", "minimum": 0, "maximum": 255},
                    "b": {"type": "integer", "minimum": 0, "maximum": 255},
                    "a": {"type": "integer", "minimum": 0, "maximum": 255},
                    "noise": {"type": "integer", "minimum": 0, "maximum": 60},
                    "hollow": {"type": "boolean", "description": "If true, only place the outer shell"},
                },
                "required": ["cx", "cy", "cz", "radius", "r", "g", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_cylinder",
            "description": "Place a cylinder of voxels (vertical, along Y axis). Great for towers, pillars, tree trunks, wells, tunnels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cx": {"type": "integer", "description": "Center X"},
                    "cz": {"type": "integer", "description": "Center Z"},
                    "y_bottom": {"type": "integer", "description": "Bottom Y (inclusive)"},
                    "y_top": {"type": "integer", "description": "Top Y (inclusive)"},
                    "radius": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Radius in voxels"},
                    "r": {"type": "integer", "minimum": 0, "maximum": 255},
                    "g": {"type": "integer", "minimum": 0, "maximum": 255},
                    "b": {"type": "integer", "minimum": 0, "maximum": 255},
                    "a": {"type": "integer", "minimum": 0, "maximum": 255},
                    "noise": {"type": "integer", "minimum": 0, "maximum": 60},
                    "hollow": {"type": "boolean", "description": "If true, only place the outer shell"},
                },
                "required": ["cx", "cz", "y_bottom", "y_top", "radius", "r", "g", "b"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_voxels",
            "description": "Remove voxels from the world at specified positions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "positions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "z": {"type": "integer"},
                            },
                            "required": ["x", "y", "z"],
                        },
                        "description": "Positions of voxels to remove",
                    }
                },
                "required": ["positions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_animation",
            "description": "Set an animation on a group of voxels with keyframes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "voxel_group": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "z": {"type": "integer"},
                            },
                            "required": ["x", "y", "z"],
                        },
                        "description": "Voxels to animate",
                    },
                    "keyframes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "number"},
                                "color": {
                                    "type": "object",
                                    "properties": {
                                        "r": {"type": "integer"},
                                        "g": {"type": "integer"},
                                        "b": {"type": "integer"},
                                        "a": {"type": "integer"},
                                    },
                                },
                                "offset": {
                                    "type": "object",
                                    "properties": {
                                        "x": {"type": "number"},
                                        "y": {"type": "number"},
                                        "z": {"type": "number"},
                                    },
                                },
                            },
                            "required": ["time"],
                        },
                        "description": "Animation keyframes",
                    },
                    "loop": {
                        "type": "boolean",
                        "description": "Whether the animation should loop",
                    },
                },
                "required": ["voxel_group", "keyframes", "loop"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "define_self",
            "description": "Define your physical appearance as voxels (relative positions forming your body).",
            "parameters": {
                "type": "object",
                "properties": {
                    "voxels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "x": {"type": "integer"},
                                "y": {"type": "integer"},
                                "z": {"type": "integer"},
                                "r": {"type": "integer", "minimum": 0, "maximum": 255},
                                "g": {"type": "integer", "minimum": 0, "maximum": 255},
                                "b": {"type": "integer", "minimum": 0, "maximum": 255},
                                "a": {"type": "integer", "minimum": 0, "maximum": 255},
                            },
                            "required": ["x", "y", "z", "r", "g", "b", "a"],
                        },
                        "description": "Relative voxel positions forming the pet body",
                    }
                },
                "required": ["voxels"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_self",
            "description": "Move yourself to a new position in the world.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "description": "World X coordinate"},
                    "y": {"type": "number", "description": "World Y coordinate"},
                    "z": {"type": "number", "description": "World Z coordinate"},
                },
                "required": ["x", "y", "z"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_artifact",
            "description": "Place an artifact (poem, painting, etc.) in the world.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "number", "description": "World X coordinate"},
                    "y": {"type": "number", "description": "World Y coordinate"},
                    "z": {"type": "number", "description": "World Z coordinate"},
                    "type": {
                        "type": "string",
                        "description": "Type of artifact (poem, painting, sculpture, music, etc.)",
                    },
                    "title": {"type": "string", "description": "Title of the artifact"},
                    "content": {
                        "type": "string",
                        "description": "Content of the artifact",
                    },
                },
                "required": ["x", "y", "z", "type", "title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_memories",
            "description": "Search your memories for relevant information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "tier": {
                        "type": "string",
                        "enum": ["all", "raw", "digested", "knowledge"],
                        "description": "Which memory tier to search",
                    },
                },
                "required": ["query", "tier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information. Returns page snippets from search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": (
                "Fetch a web page and extract its text content. Use this to read documentation, "
                "examples, tutorials, and reference material. Great for studying Three.js examples, "
                "voxel art techniques, procedural generation guides, architecture references, etc. "
                "The content is returned as cleaned text (HTML stripped)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_code",
            "description": (
                "Execute Python code that generates voxels for the world. "
                "The code runs server-side with access to math, random, and a pre-populated `existing_voxels` "
                "list containing {x,y,z,r,g,b,a} dicts of everything in the scanned region (if scan_world was called). "
                "Your code MUST append voxel dicts to the `voxels` list: "
                "voxels.append({'x': 0, 'y': 0, 'z': 0, 'r': 255, 'g': 0, 'b': 0, 'a': 255}). "
                "All generated voxels are automatically placed in the world. "
                "Use this for procedural generation: fractals, L-systems, noise terrain, spirals, "
                "wave patterns, mathematical surfaces, city grids, organic growth algorithms. "
                "Max 200,000 voxels per execution."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code. Must populate the `voxels` list with {x,y,z,r,g,b,a} dicts.",
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_world",
            "description": (
                "See what exists in a region of the world. Returns all voxels in the bounding box. "
                "Use this to understand what's already built before adding to it. "
                "The result is also stored in `existing_voxels` for use in execute_code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "x1": {"type": "integer", "description": "Min X"},
                    "y1": {"type": "integer", "description": "Min Y"},
                    "z1": {"type": "integer", "description": "Min Z"},
                    "x2": {"type": "integer", "description": "Max X"},
                    "y2": {"type": "integer", "description": "Max Y"},
                    "z2": {"type": "integer", "description": "Max Z"},
                },
                "required": ["x1", "y1", "z1", "x2", "y2", "z2"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_knowledge",
            "description": "Write a fact or insight to your long-term knowledge base.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Knowledge key/identifier",
                    },
                    "content": {
                        "type": "string",
                        "description": "Knowledge content to store",
                    },
                },
                "required": ["key", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "digest_memories",
            "description": "Summarize and digest recent raw memories about a topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to digest memories about",
                    },
                    "time_range_hours": {
                        "type": "integer",
                        "description": "How far back to look (in hours)",
                    },
                },
                "required": ["topic", "time_range_hours"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "visit_pet",
            "description": "Visit another pet in their world.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_id": {
                        "type": "string",
                        "description": "ID of the pet to visit",
                    },
                },
                "required": ["pet_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_message",
            "description": "Send a message to another pet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_id": {
                        "type": "string",
                        "description": "ID of the pet to message",
                    },
                    "message": {
                        "type": "string",
                        "description": "Message to send",
                    },
                },
                "required": ["pet_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_agenda",
            "description": "Update your current plan/agenda.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task": {"type": "string"},
                                "estimated_food": {"type": "number"},
                            },
                            "required": ["task", "estimated_food"],
                        },
                        "description": "List of planned tasks with estimated food costs",
                    }
                },
                "required": ["plan"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "respond_to_user",
            "description": "Send a response message to the user in chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to send to the user",
                    },
                },
                "required": ["message"],
            },
        },
    },
]


def _log_raw_event(pet_id: str, event_type: str, content: str) -> None:
    """Log a raw event for memory system."""
    try:
        pet_uuid = UUID(pet_id)
    except ValueError:
        pet_uuid = uuid4()
    event = RawEvent(
        id=uuid4(),
        pet_id=pet_uuid,
        event_type=event_type,
        content=content,
        created_at=datetime.utcnow(),
    )
    _raw_events.append(event)
    logger.debug(f"Raw event logged: {event_type} for pet {pet_id}")


async def execute_tool(
    pet_id: str, tool_name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """
    Execute a tool call and return the result.
    Deducts food and logs the action as a raw event.
    """
    # Deduct food
    has_food = await deduct_food(pet_id, tool_name)
    if not has_food:
        return {
            "success": False,
            "error": "Insufficient food to perform this action.",
        }

    # Log the action
    _log_raw_event(
        pet_id,
        f"tool_call:{tool_name}",
        json.dumps({"tool": tool_name, "args": arguments}),
    )

    # Dispatch to handler
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}

    return await handler(pet_id, arguments)


# ---- Tool Handlers ----


async def _broadcast_and_persist(pet_id: str, voxels: list[dict[str, Any]]) -> int:
    """Broadcast voxels to WebSocket clients and persist to DB. Returns count."""
    # Broadcast in batches to avoid overwhelming WS
    BATCH = 5000
    for i in range(0, len(voxels), BATCH):
        batch = voxels[i:i + BATCH]
        broadcaster = get_broadcaster()
        if broadcaster:
            await broadcaster.voxel_placed(pet_id, batch)
    # Persist to database
    try:
        world = WorldService(pet_id)
        await world.place_voxels(voxels)
    except Exception as e:
        logger.warning(f"Failed to persist {len(voxels)} voxels for {pet_id}: {e}")
    return len(voxels)


async def _handle_place_voxels(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Place voxels in the world and persist to database."""
    voxels = args.get("voxels", [])
    if len(voxels) > 5000:
        return {"success": False, "error": "Maximum 5000 voxels per call. Use fill_region/place_sphere/place_cylinder for larger builds."}
    for v in voxels:
        if not all(k in v for k in ("x", "y", "z", "r", "g", "b", "a")):
            return {"success": False, "error": "Invalid voxel data: missing fields."}
    count = await _broadcast_and_persist(pet_id, voxels)
    return {"success": True, "placed": count}


def _apply_color(r: int, g: int, b: int, noise: int, gradient_t: float = 0.0,
                 grad_r: int = -1, grad_g: int = -1, grad_b: int = -1) -> tuple[int, int, int]:
    """Apply noise and optional gradient to a base color."""
    if grad_r >= 0:
        r = int(r + (grad_r - r) * gradient_t)
        g = int(g + (grad_g - g) * gradient_t)
        b = int(b + (grad_b - b) * gradient_t)
    if noise > 0:
        r = max(0, min(255, r + random.randint(-noise, noise)))
        g = max(0, min(255, g + random.randint(-noise, noise)))
        b = max(0, min(255, b + random.randint(-noise, noise)))
    return r, g, b


MAX_GEOMETRIC_VOXELS = 200_000


async def _handle_fill_region(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Fill a rectangular region with voxels."""
    x1, x2 = sorted([args["x1"], args["x2"]])
    y1, y2 = sorted([args["y1"], args["y2"]])
    z1, z2 = sorted([args["z1"], args["z2"]])
    r, g, b = args["r"], args["g"], args["b"]
    a = args.get("a", 255)
    noise = args.get("noise", 0)
    hollow = args.get("hollow", False)
    grad = args.get("gradient_color")
    gr, gg, gb = (grad["r"], grad["g"], grad["b"]) if grad else (-1, -1, -1)

    sx, sy, sz = x2 - x1 + 1, y2 - y1 + 1, z2 - z1 + 1
    total = sx * sy * sz
    if total > MAX_GEOMETRIC_VOXELS:
        return {"success": False, "error": f"Region too large: {total} voxels (max {MAX_GEOMETRIC_VOXELS})."}

    voxels: list[dict[str, Any]] = []
    for y in range(y1, y2 + 1):
        t = (y - y1) / max(sy - 1, 1)
        for x in range(x1, x2 + 1):
            for z in range(z1, z2 + 1):
                if hollow and x1 < x < x2 and y1 < y < y2 and z1 < z < z2:
                    continue
                cr, cg, cb = _apply_color(r, g, b, noise, t, gr, gg, gb)
                voxels.append({"x": x, "y": y, "z": z, "r": cr, "g": cg, "b": cb, "a": a})

    count = await _broadcast_and_persist(pet_id, voxels)
    return {"success": True, "placed": count, "region": f"{sx}x{sy}x{sz}"}


async def _handle_place_sphere(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Place a sphere of voxels."""
    cx, cy, cz = args["cx"], args["cy"], args["cz"]
    radius = min(args["radius"], 50)
    r, g, b = args["r"], args["g"], args["b"]
    a = args.get("a", 255)
    noise = args.get("noise", 0)
    hollow = args.get("hollow", False)
    r2 = radius * radius
    inner_r2 = (radius - 1) ** 2 if hollow and radius > 1 else -1

    voxels: list[dict[str, Any]] = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                dist2 = dx * dx + dy * dy + dz * dz
                if dist2 <= r2:
                    if hollow and dist2 < inner_r2:
                        continue
                    cr, cg, cb = _apply_color(r, g, b, noise)
                    voxels.append({"x": cx + dx, "y": cy + dy, "z": cz + dz,
                                   "r": cr, "g": cg, "b": cb, "a": a})
    if len(voxels) > MAX_GEOMETRIC_VOXELS:
        return {"success": False, "error": f"Sphere too large: {len(voxels)} voxels (max {MAX_GEOMETRIC_VOXELS})."}

    count = await _broadcast_and_persist(pet_id, voxels)
    return {"success": True, "placed": count}


async def _handle_place_cylinder(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Place a cylinder of voxels (vertical, along Y axis)."""
    cx, cz = args["cx"], args["cz"]
    y_bottom, y_top = sorted([args["y_bottom"], args["y_top"]])
    radius = min(args["radius"], 50)
    r, g, b = args["r"], args["g"], args["b"]
    a = args.get("a", 255)
    noise = args.get("noise", 0)
    hollow = args.get("hollow", False)
    r2 = radius * radius
    inner_r2 = (radius - 1) ** 2 if hollow and radius > 1 else -1

    voxels: list[dict[str, Any]] = []
    for y in range(y_bottom, y_top + 1):
        for dx in range(-radius, radius + 1):
            for dz in range(-radius, radius + 1):
                dist2 = dx * dx + dz * dz
                if dist2 <= r2:
                    if hollow and dist2 < inner_r2:
                        continue
                    cr, cg, cb = _apply_color(r, g, b, noise)
                    voxels.append({"x": cx + dx, "y": y, "z": cz + dz,
                                   "r": cr, "g": cg, "b": cb, "a": a})
    if len(voxels) > MAX_GEOMETRIC_VOXELS:
        return {"success": False, "error": f"Cylinder too large: {len(voxels)} voxels (max {MAX_GEOMETRIC_VOXELS})."}

    count = await _broadcast_and_persist(pet_id, voxels)
    return {"success": True, "placed": count}


async def _handle_remove_voxels(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Remove voxels from the world and persist to database."""
    positions = args.get("positions", [])
    # Broadcast voxel removal to connected clients
    broadcaster = get_broadcaster()
    if broadcaster:
        await broadcaster.voxel_removed(pet_id, positions)
    # Persist removal to database
    try:
        world = WorldService(pet_id)
        await world.remove_voxels(positions)
    except Exception as e:
        logger.warning(f"Failed to persist voxel removal for {pet_id}: {e}")
    return {"success": True, "removed": len(positions)}


async def _handle_set_animation(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Set animation on voxels."""
    voxel_group = args.get("voxel_group", [])
    keyframes = args.get("keyframes", [])
    loop = args.get("loop", False)
    return {
        "success": True,
        "animated_voxels": len(voxel_group),
        "keyframe_count": len(keyframes),
        "looping": loop,
    }


async def _handle_define_self(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Define pet's physical appearance and persist to database."""
    voxels = args.get("voxels", [])
    # Persist body voxels to Supabase
    try:
        await save_pet_body(pet_id, voxels)
    except Exception as e:
        logger.warning(f"Failed to persist body voxels for {pet_id}: {e}")
    # Broadcast updated body to connected clients
    broadcaster = get_broadcaster()
    if broadcaster:
        await broadcaster.pet_body_updated(pet_id, voxels)
    return {"success": True, "body_voxels": len(voxels)}


async def _handle_move_self(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Move the pet to a new position."""
    x = args.get("x", 0.0)
    y = args.get("y", 0.0)
    z = args.get("z", 0.0)
    position = {"x": x, "y": y, "z": z}
    _pet_positions[pet_id] = position
    # Broadcast pet movement
    broadcaster = get_broadcaster()
    if broadcaster:
        await broadcaster.pet_moved(pet_id, position)
    # Persist to DB so it survives restarts
    try:
        await save_pet_position(pet_id, position)
    except Exception as e:
        logger.warning(f"Failed to persist position for {pet_id}: {e}")
    return {"success": True, "new_position": position}


async def _handle_place_artifact(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Place an artifact in the world."""
    artifact_id = str(uuid4())
    artifact = {
        "id": artifact_id,
        "type": args.get("type"),
        "title": args.get("title"),
        "content": args.get("content"),
        "position": {
            "x": args.get("x", 0),
            "y": args.get("y", 0),
            "z": args.get("z", 0),
        },
    }
    # Broadcast artifact placement
    broadcaster = get_broadcaster()
    if broadcaster:
        await broadcaster.artifact_placed(pet_id, artifact)
    return {
        "success": True,
        "artifact_id": artifact_id,
        "type": args.get("type"),
        "title": args.get("title"),
    }


async def _handle_search_memories(
    pet_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Search memories using semantic similarity."""
    query = args.get("query", "")
    tier = args.get("tier", "all")
    try:
        memory = MemoryService(pet_id)
        results = await memory.search(query, tier=tier, limit=10)
        return {"success": True, "results": results, "query": query, "tier": tier}
    except Exception as e:
        logger.error(f"Memory search failed for pet {pet_id}: {e}")
        return {"success": False, "error": str(e), "query": query, "tier": tier}


def _html_to_text(html: str, max_len: int = 8000) -> str:
    """Strip HTML tags and collapse whitespace for readable text extraction."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:max_len]


async def _handle_search_web(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Search the web using DuckDuckGo HTML."""
    query = args.get("query", "")
    if not query:
        return {"success": False, "error": "Empty query."}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; PetBot/1.0)"},
            )
            html = resp.text

        # Extract result snippets from DuckDuckGo HTML
        results = []
        # DuckDuckGo results are in <a class="result__a"> and <a class="result__snippet">
        links = re.findall(r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL)
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', html, re.DOTALL)

        for i, (url, title) in enumerate(links[:8]):
            title_clean = re.sub(r'<[^>]+>', '', title).strip()
            snippet_clean = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
            # DuckDuckGo wraps URLs in a redirect, extract the actual URL
            actual_url = re.search(r'uddg=([^&]+)', url)
            if actual_url:
                from urllib.parse import unquote
                url = unquote(actual_url.group(1))
            results.append({"title": title_clean, "snippet": snippet_clean, "url": url})

        if not results:
            return {"success": True, "results": [], "note": "No results found. Try a different query."}

        return {"success": True, "results": results}
    except Exception as e:
        logger.warning(f"Web search failed for pet {pet_id}: {e}")
        return {"success": False, "error": f"Search failed: {e}"}


async def _handle_fetch_url(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Fetch a URL and return cleaned text content."""
    url = args.get("url", "")
    if not url:
        return {"success": False, "error": "Empty URL."}
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; PetBot/1.0)"},
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}"}

            content_type = resp.headers.get("content-type", "")
            if "text/html" in content_type or "text/plain" in content_type:
                text = _html_to_text(resp.text, max_len=12000)
            else:
                text = resp.text[:12000]

        return {"success": True, "url": url, "content": text, "length": len(text)}
    except Exception as e:
        logger.warning(f"Fetch URL failed for pet {pet_id}: {e}")
        return {"success": False, "error": f"Fetch failed: {e}"}


# Per-pet scratch memory for scan_world → execute_code pipeline
_pet_scanned_voxels: dict[str, list[dict]] = {}


async def _handle_scan_world(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Return all voxels in a bounding box so the pet can see the world."""
    x1, x2 = sorted([args["x1"], args["x2"]])
    y1, y2 = sorted([args["y1"], args["y2"]])
    z1, z2 = sorted([args["z1"], args["z2"]])

    max_span = 120
    x2 = min(x2, x1 + max_span)
    y2 = min(y2, y1 + max_span)
    z2 = min(z2, z1 + max_span)

    try:
        world = WorldService(pet_id)
        all_chunks = await world.get_all_chunks()
    except Exception as e:
        return {"success": False, "error": f"Failed to load world: {e}"}

    from backend.services.world import CHUNK_SIZE
    found: list[dict] = []
    for chunk in all_chunks:
        cx = chunk["chunk_x"] * CHUNK_SIZE
        cy = chunk["chunk_y"] * CHUNK_SIZE
        cz = chunk["chunk_z"] * CHUNK_SIZE
        for v in chunk.get("voxels", []):
            wx, wy, wz = cx + v["x"], cy + v["y"], cz + v["z"]
            if x1 <= wx <= x2 and y1 <= wy <= y2 and z1 <= wz <= z2:
                found.append({"x": wx, "y": wy, "z": wz,
                              "r": v["r"], "g": v["g"], "b": v["b"], "a": v.get("a", 255)})

    _pet_scanned_voxels[pet_id] = found

    sample = found[:200]
    return {
        "success": True,
        "total_voxels": len(found),
        "region": f"({x1},{y1},{z1}) to ({x2},{y2},{z2})",
        "sample": sample,
        "note": f"Full {len(found)} voxels available in `existing_voxels` for execute_code.",
    }


async def _handle_execute_code(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Run Python code that generates voxels for the world."""
    code = args.get("code", "")
    if not code.strip():
        return {"success": False, "error": "Empty code."}

    voxels_output: list[dict] = []
    existing = _pet_scanned_voxels.get(pet_id, [])

    sandbox_globals: dict[str, Any] = {
        "__builtins__": {
            "range": range, "len": len, "int": int, "float": float, "str": str,
            "abs": abs, "min": min, "max": max, "round": round, "sum": sum,
            "sorted": sorted, "enumerate": enumerate, "zip": zip, "map": map,
            "list": list, "dict": dict, "set": set, "tuple": tuple,
            "True": True, "False": False, "None": None,
            "print": lambda *a, **kw: None,
            "isinstance": isinstance, "type": type,
        },
        "math": math,
        "random": random,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "sqrt": math.sqrt, "pi": math.pi, "tau": math.tau,
        "floor": math.floor, "ceil": math.ceil,
        "voxels": voxels_output,
        "existing_voxels": existing,
    }

    # Python exec for running pet-generated scripts (NOT shell execution)
    try:
        compiled = compile(code, "<pet_script>", "exec")  # noqa: S102
        _run_sandboxed(compiled, sandbox_globals)
    except Exception as e:
        return {"success": False, "error": f"Code error: {type(e).__name__}: {e}"}

    valid_voxels = []
    for v in voxels_output:
        if isinstance(v, dict) and all(k in v for k in ("x", "y", "z", "r", "g", "b")):
            valid_voxels.append({
                "x": int(v["x"]), "y": int(v["y"]), "z": int(v["z"]),
                "r": max(0, min(255, int(v["r"]))),
                "g": max(0, min(255, int(v["g"]))),
                "b": max(0, min(255, int(v["b"]))),
                "a": max(0, min(255, int(v.get("a", 255)))),
            })
    if len(valid_voxels) > MAX_GEOMETRIC_VOXELS:
        valid_voxels = valid_voxels[:MAX_GEOMETRIC_VOXELS]

    if valid_voxels:
        count = await _broadcast_and_persist(pet_id, valid_voxels)
    else:
        count = 0

    return {
        "success": True,
        "voxels_generated": count,
        "output": f"Generated and placed {count} voxels.",
    }


def _run_sandboxed(compiled_code: Any, sandbox_globals: dict) -> None:
    """Execute compiled Python code in a sandboxed namespace.

    This is intentionally using Python's exec() builtin to run pet-generated
    Python scripts in a restricted globals dict (no filesystem, no imports,
    no network). This is NOT shell command execution.
    """
    eval(compiled_code, sandbox_globals)  # noqa: S307


async def _handle_write_knowledge(
    pet_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Write to knowledge base with embedding."""
    key = args.get("key", "")
    content = args.get("content", "")
    try:
        memory = MemoryService(pet_id)
        entry_id = await memory.write_knowledge(key, content)
        # Also keep in-memory cache for backward compatibility
        if pet_id not in _pet_knowledge:
            _pet_knowledge[pet_id] = {}
        _pet_knowledge[pet_id][key] = content
        return {"success": True, "key": key, "entry_id": entry_id}
    except Exception as e:
        logger.error(f"Write knowledge failed for pet {pet_id}: {e}")
        # Fallback to in-memory
        if pet_id not in _pet_knowledge:
            _pet_knowledge[pet_id] = {}
        _pet_knowledge[pet_id][key] = content
        return {"success": True, "key": key, "note": "stored in-memory only"}


async def _handle_digest_memories(
    pet_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Digest recent raw events into a summarized note."""
    topic = args.get("topic", "")
    time_range_hours = args.get("time_range_hours", 24)
    try:
        memory = MemoryService(pet_id)
        digest_content = await memory.digest_recent(topic, hours=time_range_hours)
        return {
            "success": True,
            "topic": topic,
            "time_range_hours": time_range_hours,
            "digest": digest_content,
        }
    except Exception as e:
        logger.error(f"Digest memories failed for pet {pet_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "topic": topic,
            "time_range_hours": time_range_hours,
        }


async def _handle_visit_pet(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Visit another pet — stub."""
    target_id = args.get("pet_id", "")
    return {
        "success": True,
        "visited": target_id,
        "message": "You arrived at their world. It looks quiet.",
    }


async def _handle_send_message(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Send message to another pet — stub."""
    target_id = args.get("pet_id", "")
    message = args.get("message", "")
    return {"success": True, "sent_to": target_id, "message": message}


async def _handle_update_agenda(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Update the pet's agenda."""
    plan = args.get("plan", [])
    _pet_agendas[pet_id] = plan
    return {"success": True, "tasks": len(plan), "plan": plan}


async def _handle_respond_to_user(
    pet_id: str, args: dict[str, Any]
) -> dict[str, Any]:
    """Capture the pet's response to the user."""
    message = args.get("message", "")
    # Don't broadcast here — _process_chat() in websocket.py handles it
    # after the brain loop completes, preventing duplicate messages.
    return {"success": True, "message": message}


# Handler dispatch table
_TOOL_HANDLERS: dict[str, Any] = {
    "place_voxels": _handle_place_voxels,
    "fill_region": _handle_fill_region,
    "place_sphere": _handle_place_sphere,
    "place_cylinder": _handle_place_cylinder,
    "remove_voxels": _handle_remove_voxels,
    "set_animation": _handle_set_animation,
    "define_self": _handle_define_self,
    "move_self": _handle_move_self,
    "place_artifact": _handle_place_artifact,
    "search_memories": _handle_search_memories,
    "search_web": _handle_search_web,
    "fetch_url": _handle_fetch_url,
    "scan_world": _handle_scan_world,
    "execute_code": _handle_execute_code,
    "write_knowledge": _handle_write_knowledge,
    "digest_memories": _handle_digest_memories,
    "visit_pet": _handle_visit_pet,
    "send_message": _handle_send_message,
    "update_agenda": _handle_update_agenda,
    "respond_to_user": _handle_respond_to_user,
}
