"""Tool executor for pet brain actions."""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from backend.models.memory import RawEvent
from backend.services.food import deduct_food
from backend.services.memory import MemoryService
from backend.services.events import get_broadcaster

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
                        "maxItems": 1000,
                        "description": "Array of voxels to place (max 1000)",
                    }
                },
                "required": ["voxels"],
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
            "description": "Search the web for information.",
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
            "name": "execute_code",
            "description": "Execute code in a sandboxed environment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Programming language",
                    },
                    "code": {"type": "string", "description": "Code to execute"},
                },
                "required": ["language", "code"],
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


async def _handle_place_voxels(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Place voxels in the world."""
    voxels = args.get("voxels", [])
    if len(voxels) > 1000:
        return {"success": False, "error": "Maximum 1000 voxels per call."}
    # Validate voxel data
    for v in voxels:
        if not all(k in v for k in ("x", "y", "z", "r", "g", "b", "a")):
            return {"success": False, "error": "Invalid voxel data: missing fields."}
    # Broadcast voxel placement
    broadcaster = get_broadcaster()
    if broadcaster:
        await broadcaster.voxel_placed(pet_id, voxels)
    return {"success": True, "placed": len(voxels)}


async def _handle_remove_voxels(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Remove voxels from the world."""
    positions = args.get("positions", [])
    # Broadcast voxel removal
    broadcaster = get_broadcaster()
    if broadcaster:
        await broadcaster.voxel_removed(pet_id, positions)
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
    """Define pet's physical appearance."""
    voxels = args.get("voxels", [])
    return {"success": True, "body_voxels": len(voxels)}


async def _handle_move_self(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Move the pet to a new position."""
    x = args.get("x", 0.0)
    y = args.get("y", 0.0)
    z = args.get("z", 0.0)
    _pet_positions[pet_id] = {"x": x, "y": y, "z": z}
    # Broadcast pet movement
    broadcaster = get_broadcaster()
    if broadcaster:
        await broadcaster.pet_moved(pet_id, {"x": x, "y": y, "z": z})
    return {"success": True, "new_position": {"x": x, "y": y, "z": z}}


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


async def _handle_search_web(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Search the web — stub."""
    query = args.get("query", "")
    return {
        "success": True,
        "results": [
            {
                "title": f"Search result for: {query}",
                "snippet": "Web search is not yet implemented. Results will appear here in the future.",
                "url": "https://example.com",
            }
        ],
    }


async def _handle_execute_code(pet_id: str, args: dict[str, Any]) -> dict[str, Any]:
    """Execute code — stub."""
    language = args.get("language", "unknown")
    return {
        "success": True,
        "output": f"Code execution ({language}) is not yet implemented.",
        "exit_code": 0,
    }


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
    "remove_voxels": _handle_remove_voxels,
    "set_animation": _handle_set_animation,
    "define_self": _handle_define_self,
    "move_self": _handle_move_self,
    "place_artifact": _handle_place_artifact,
    "search_memories": _handle_search_memories,
    "search_web": _handle_search_web,
    "execute_code": _handle_execute_code,
    "write_knowledge": _handle_write_knowledge,
    "digest_memories": _handle_digest_memories,
    "visit_pet": _handle_visit_pet,
    "send_message": _handle_send_message,
    "update_agenda": _handle_update_agenda,
    "respond_to_user": _handle_respond_to_user,
}
