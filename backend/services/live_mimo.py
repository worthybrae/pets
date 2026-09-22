"""Durable, server-owned life loop for the Mimo prototype.

The browser only renders this state. A separate worker makes decisions and advances
projects even when nobody has the page open. Plans are compact build instructions;
the frontend compiles them into voxels, and this module uses their footprints for
spatial observation and collision checks.
"""

from __future__ import annotations

import json
import heapq
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from backend.services.crafting import BLOCKS, RECIPES, SMELTING, add_item, can_harvest, craft, smelt, take_items

STATION = {"kind": "station", "site": {"x": 48, "z": 0}, "variant": 0,
           "observation": "A wide, empty stretch of sky above the eastern plain.", "clearance": 41}
RADII = {"station": 20, "landing_pad": 6, "boardwalk": 6, "greenhouse": 5,
         "observatory": 5, "sculpture": 5, "grove": 7, "plaza": 7}
BUILD_KINDS = [kind for kind in RADII if kind != "station"]
BLOCK_TYPES = set(BLOCKS) | {"air"}
LOOSE_BLOCKS = {kind for kind, properties in BLOCKS.items() if properties.get("gravity")}
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "mimo.sqlite3"


def now() -> float:
    return time.time()


def distance(a: dict, b: dict) -> float:
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def terrain_height(x: int, z: int) -> int:
    if math.hypot(x, z) < 17 or math.hypot(x - 48, z) < 27:
        return 0
    wave = math.sin(x * 0.085) + math.cos(z * 0.075) + math.sin((x + z) * 0.037)
    return 3 if wave > 1.65 else 2 if wave > 1.15 else 1 if wave > 0.65 else 0


def new_state(timestamp: float) -> dict:
    return {
        "name": "Mimo", "born_at": timestamp,
        "personality": {"curiosity": 82, "creativity": 91, "sociability": 66, "patience": 73},
        "position": {"x": 73.0, "y": 1.0, "z": 0.0}, "energy": 100.0, "mood": 70.0,
        "explore_target": None,
        "inventory": {"oak_log": 8, "cobblestone": 12, "coal": 4, "iron_ore": 3},
        "plans": [STATION], "currentIndex": 0, "progress": 100.0,
        "status": "thinking", "last_thought": "I wonder what belongs beside my station.",
        "last_observation": "The orbital station is complete; the world around it is open.",
        "next_tick_at": timestamp, "last_tick_at": timestamp,
        "last_action_at": timestamp, "last_hello_at": None, "last_error": None,
        "decision_day": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
        "decisions_today": 0,
    }


def normalize_state(state: dict) -> dict:
    # Preserve worlds created by earlier versions of the local prototype.
    state.setdefault("inventory", {"oak_log": 8, "cobblestone": 12, "coal": 4, "iron_ore": 3})
    state.setdefault("decision_day", datetime.fromtimestamp(state["born_at"], timezone.utc).date().isoformat())
    state.setdefault("decisions_today", 0)
    state.setdefault("explore_target", None)
    state["position"].setdefault("y", terrain_height(round(state["position"]["x"]), round(state["position"]["z"])) + 1)
    return state


def next_walk_position(state: dict, target: dict, max_steps: int = 8) -> dict:
    """A* over terrain and existing footprints; return one bounded movement step."""
    start = (round(state["position"]["x"]), round(state["position"]["z"]))
    end = (round(target["x"]), round(target["z"]))
    if start == end:
        return {"x": float(end[0]), "y": float(terrain_height(*end) + 1), "z": float(end[1])}
    completed = state["plans"][:state["currentIndex"]]
    def blocked(x: int, z: int) -> bool:
        return any(math.hypot(x - plan["site"]["x"], z - plan["site"]["z"]) < RADII[plan["kind"]] + 1
                   for plan in completed)
    queue = [(abs(start[0] - end[0]) + abs(start[1] - end[1]), 0.0, start)]
    previous = {start: None}
    best_cost = {start: 0.0}
    for _ in range(12000):
        if not queue:
            break
        _, cost, point = heapq.heappop(queue)
        if point == end:
            break
        if cost > best_cost.get(point, math.inf):
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (point[0] + dx, point[1] + dz)
            if blocked(*neighbor) or abs(neighbor[0] - start[0]) > 100 or abs(neighbor[1] - start[1]) > 100:
                continue
            slope = abs(terrain_height(*neighbor) - terrain_height(*point))
            next_cost = cost + 1 + slope * 1.5
            if next_cost >= best_cost.get(neighbor, math.inf):
                continue
            best_cost[neighbor] = next_cost
            previous[neighbor] = point
            heuristic = abs(neighbor[0] - end[0]) + abs(neighbor[1] - end[1])
            heapq.heappush(queue, (next_cost + heuristic, next_cost, neighbor))
    if end not in previous:
        raise ValueError("No traversable route to the chosen site")
    path = []
    point = end
    while point != start:
        path.append(point)
        point = previous[point]
    point = path[-min(max_steps, len(path))]
    return {"x": float(point[0]), "y": float(terrain_height(*point) + 1), "z": float(point[1])}


class MimoStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or os.environ.get("MIMO_DB_PATH") or DEFAULT_DB)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS mimo_state (id INTEGER PRIMARY KEY CHECK (id=1), data TEXT NOT NULL, lease_until REAL NOT NULL DEFAULT 0)")
            db.execute("CREATE TABLE IF NOT EXISTS mimo_events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL, text TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS mimo_worker (id INTEGER PRIMARY KEY CHECK (id=1), seen_at REAL NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS mimo_blocks (x INTEGER NOT NULL, y INTEGER NOT NULL, z INTEGER NOT NULL, material TEXT NOT NULL, PRIMARY KEY(x,y,z))")
            timestamp = now()
            inserted = db.execute("INSERT OR IGNORE INTO mimo_state (id,data) VALUES (1,?)", (json.dumps(new_state(timestamp)),))
            if inserted.rowcount:
                db.execute("INSERT INTO mimo_events (at,kind,text) VALUES (?,?,?)", (timestamp, "birth", "Mimo's orbital station is ready. Its own life begins now."))

    def snapshot(self) -> dict:
        with self.connect() as db:
            state = normalize_state(json.loads(db.execute("SELECT data FROM mimo_state WHERE id=1").fetchone()["data"]))
            state["events"] = [dict(row) for row in db.execute(
                "SELECT id,at,kind,text FROM mimo_events ORDER BY id DESC LIMIT 12"
            ).fetchall()]
            worker = db.execute("SELECT seen_at FROM mimo_worker WHERE id=1").fetchone()
            state["worker_last_seen_at"] = worker["seen_at"] if worker else None
            state["block_edits"] = [dict(row) for row in db.execute(
                "SELECT x,y,z,material FROM mimo_blocks ORDER BY x,y,z LIMIT 20000"
            ).fetchall()]
            state["catalog"] = BLOCKS
            state["recipes"] = RECIPES
            return state

    def block_edits(self) -> list[dict]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT x,y,z,material FROM mimo_blocks").fetchall()]

    def put_block(self, x: int, y: int, z: int, material: str) -> None:
        if material not in BLOCK_TYPES or not (-8 <= y <= 128) or abs(x) > 4096 or abs(z) > 4096:
            raise ValueError("Invalid block position or material")
        with self.connect() as db:
            db.execute("INSERT INTO mimo_blocks(x,y,z,material) VALUES(?,?,?,?) ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material",
                       (x, y, z, material))

    def material_at(self, x: int, y: int, z: int) -> str:
        with self.connect() as db:
            row = db.execute("SELECT material FROM mimo_blocks WHERE x=? AND y=? AND z=?", (x, y, z)).fetchone()
        return row["material"] if row else base_material(x, y, z)

    def nearby_stations(self, position: dict, radius: int = 6) -> set[str]:
        with self.connect() as db:
            rows = db.execute("SELECT x,z,material FROM mimo_blocks WHERE material IN ('crafting_table','furnace')").fetchall()
        return {row["material"] for row in rows if math.hypot(row["x"] - position["x"], row["z"] - position["z"]) <= radius}

    def step_loose_blocks(self) -> int:
        """Move placed sand and gravel down one cell when unsupported."""
        moved = 0
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT x,y,z,material FROM mimo_blocks WHERE material IN ('sand','gravel') ORDER BY y ASC").fetchall()
            edits = {(row["x"], row["y"], row["z"]): row["material"] for row in db.execute(
                "SELECT x,y,z,material FROM mimo_blocks"
            ).fetchall()}
            for row in rows:
                x, y, z, material = row["x"], row["y"], row["z"], row["material"]
                below = edits.get((x, y - 1, z), base_material(x, y - 1, z))
                if below not in ("air", "water") or y <= -5:
                    continue
                db.execute("INSERT INTO mimo_blocks(x,y,z,material) VALUES(?,?,?,'air') ON CONFLICT(x,y,z) DO UPDATE SET material='air'", (x, y, z))
                db.execute("INSERT INTO mimo_blocks(x,y,z,material) VALUES(?,?,?,?) ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material", (x, y - 1, z, material))
                edits[(x, y, z)] = "air"
                edits[(x, y - 1, z)] = material
                moved += 1
        return moved

    def heartbeat(self, timestamp: float | None = None) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO mimo_worker(id,seen_at) VALUES(1,?) ON CONFLICT(id) DO UPDATE SET seen_at=excluded.seen_at", (timestamp or now(),))

    def claim_due(self, timestamp: float) -> dict | None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data,lease_until FROM mimo_state WHERE id=1").fetchone()
            state = normalize_state(json.loads(row["data"]))
            if state["next_tick_at"] > timestamp or row["lease_until"] > timestamp:
                return None
            db.execute("UPDATE mimo_state SET lease_until=? WHERE id=1", (timestamp + 180,))
            return state

    def finish(self, state: dict, event: tuple[str, str] | None = None,
               block_edit: tuple[int, int, int, str] | None = None) -> None:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = json.loads(db.execute("SELECT data FROM mimo_state WHERE id=1").fetchone()["data"])
            # A greeting can arrive while the model is thinking. Keep it when saving.
            if current.get("last_hello_at") and (not state.get("last_hello_at") or current["last_hello_at"] > state["last_hello_at"]):
                state["last_hello_at"] = current["last_hello_at"]
                state["mood"] = min(100, max(state["mood"], current["mood"]))
            db.execute("UPDATE mimo_state SET data=?,lease_until=0 WHERE id=1", (json.dumps(state),))
            if block_edit:
                db.execute("INSERT INTO mimo_blocks(x,y,z,material) VALUES(?,?,?,?) ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material", block_edit)
            if event:
                db.execute("INSERT INTO mimo_events(at,kind,text) VALUES(?,?,?)", (now(), *event))

    def greet(self) -> dict:
        timestamp = now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            state = normalize_state(json.loads(db.execute("SELECT data FROM mimo_state WHERE id=1").fetchone()["data"]))
            state["mood"] = min(100, state["mood"] + 5)
            state["last_hello_at"] = timestamp
            state["next_tick_at"] = min(state["next_tick_at"], timestamp + 5)
            db.execute("UPDATE mimo_state SET data=? WHERE id=1", (json.dumps(state),))
            db.execute("INSERT INTO mimo_events(at,kind,text) VALUES(?,?,?)", (timestamp, "hello", "You said hello to Mimo."))
            return {"mood": state["mood"], "noticed_at": timestamp}

    def owner_action(self, action: str, item: str) -> dict:
        """Let the owner help craft, place a workstation, or smelt using Mimo's inventory."""
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT data,lease_until FROM mimo_state WHERE id=1").fetchone()
            if row["lease_until"] > now():
                raise RuntimeError("Mimo is busy; try again in a moment")
            state = normalize_state(json.loads(row["data"]))
            position = state["position"]
            stations = {machine["material"] for machine in db.execute(
                "SELECT x,z,material FROM mimo_blocks WHERE material IN ('crafting_table','furnace')"
            ).fetchall() if math.hypot(machine["x"] - position["x"], machine["z"] - position["z"]) <= 6}
            if action == "craft":
                state["inventory"] = craft(state["inventory"], item, stations)
                message = f"You crafted {item.replace('_', ' ')} for Mimo."
            elif action == "place_machine":
                if item not in ("crafting_table", "furnace"):
                    raise ValueError("Only a crafting table or furnace can be placed here")
                inventory = take_items(state["inventory"], {item: 1})
                px, pz = round(position["x"]), round(position["z"])
                candidate = None
                for dx, dz in ((2, 0), (0, 2), (-2, 0), (0, -2), (3, 0), (0, 3), (-3, 0), (0, -3)):
                    x, z = px + dx, pz + dz
                    y = terrain_height(x, z) + 1
                    row_at = db.execute("SELECT material FROM mimo_blocks WHERE x=? AND y=? AND z=?", (x, y, z)).fetchone()
                    if (row_at["material"] if row_at else base_material(x, y, z)) == "air":
                        candidate = (x, y, z)
                        break
                if candidate is None:
                    raise ValueError("No open block beside Mimo for that machine")
                db.execute("INSERT INTO mimo_blocks(x,y,z,material) VALUES(?,?,?,?) ON CONFLICT(x,y,z) DO UPDATE SET material=excluded.material", (*candidate, item))
                state["inventory"] = inventory
                message = f"You placed {item.replace('_', ' ')} beside Mimo."
            elif action == "smelt":
                state["inventory"] = smelt(state["inventory"], item, stations)
                message = f"You smelted {item.replace('_', ' ')} for Mimo."
            else:
                raise ValueError("Unknown owner action")
            db.execute("UPDATE mimo_state SET data=? WHERE id=1", (json.dumps(state),))
            db.execute("INSERT INTO mimo_events(at,kind,text) VALUES(?,?,?)", (now(), "owner", message))
            return {"message": message, "inventory": state["inventory"]}


def base_material(x: int, y: int, z: int) -> str:
    if y < -5:
        return "bedrock"
    if y == -5:
        return "bedrock"
    if -4 <= y < -1:
        ore_seed = abs(x * 31 + z * 17 + y * 101)
        return "iron_ore" if ore_seed % 37 == 0 else "coal_ore" if ore_seed % 19 == 0 else "stone"
    if y == -1:
        return "dirt"
    height = terrain_height(x, z)
    if y == 0 and ((x + 5) / 3.2) ** 2 + ((z - 4) / 2.4) ** 2 < 1:
        return "water"
    if y == height:
        return "grass"
    if 0 <= y < height:
        return "dirt" if y >= height - 1 else "stone"
    return "air"


def observe_world(state: dict, edits: list[dict] | None = None) -> dict:
    """Give the brain landmarks and validated free sites from the persisted world."""
    plans = state["plans"]
    origin = plans[-1]["site"]
    features = [{"kind": plan["kind"], "x": plan["site"]["x"], "z": plan["site"]["z"],
                 "radius": RADII[plan["kind"]], "height": 42 if plan["kind"] == "station" else 18}
                for plan in plans]
    features.append({"kind": "pond", "x": -5, "z": 4, "radius": 4, "height": 0})
    features.append({"kind": "village", "x": 0, "z": 0, "radius": 11, "height": 6})
    candidates = []
    for radius in (15, 22, 30, 39, 50, 62):
        for step in range(24):
            angle = step * math.pi / 12
            point = {"x": round(origin["x"] + math.cos(angle) * radius),
                     "z": round(origin["z"] + math.sin(angle) * radius)}
            if any(distance(point, {"x": feature["x"], "z": feature["z"]}) < feature["radius"] + 10
                   for feature in features):
                continue
            if any(terrain_height(x, z) != 0 for x in range(point["x"] - 7, point["x"] + 8)
                   for z in range(point["z"] - 7, point["z"] + 8)):
                continue
            nearest = min(features, key=lambda feature: distance(point, {"x": feature["x"], "z": feature["z"]}))
            candidates.append({"id": len(candidates), **point, "clearance": 15,
                               "nearest": nearest["kind"],
                               "distance_to_nearest": round(distance(point, {"x": nearest["x"], "z": nearest["z"]}))})
            if len(candidates) >= 16:
                break
        if len(candidates) >= 16:
            break
    edits = edits or []
    edited = {(block["x"], block["y"], block["z"]): block["material"] for block in edits}
    px, pz = round(state["position"]["x"]), round(state["position"]["z"])
    columns = []
    for x, z in ((px, pz), (px + 2, pz), (px - 2, pz), (px, pz + 2), (px, pz - 2)):
        columns.append({"x": x, "z": z,
                        "layers": [{"y": y, "material": edited.get((x, y, z), base_material(x, y, z))}
                                   for y in range(3, -5, -1)]})
    return {"pet_position": state["position"], "features": features[-14:],
            "pond": {"x": -5, "z": 4}, "candidate_sites": candidates,
            "nearby_columns": columns, "loose_blocks": [block for block in edits if block["material"] in LOOSE_BLOCKS][:20],
            "nearby_stations": [block["material"] for block in edits if block["material"] in ("crafting_table", "furnace")
                                and math.hypot(block["x"] - px, block["z"] - pz) <= 6],
            "inventory": state["inventory"], "recipes": RECIPES, "smelting": SMELTING,
            "recent_builds": [plan["kind"] for plan in plans[-8:]],
            "last_hello_at": state["last_hello_at"]}


def _model_decision(state: dict, observation: dict, events: list[dict]) -> dict:
    model = os.environ.get("MIMO_MODEL", "gpt-6-luna")
    api_key = os.environ.get("MIMO_MODEL_API_KEY") or os.environ.get("OPENAI_API_KEY")
    url = os.environ.get("MIMO_MODEL_URL", "https://api.openai.com/v1/chat/completions")
    is_openai_api = urlsplit(url).hostname == "api.openai.com"
    if not model or (not api_key and is_openai_api):
        raise RuntimeError("Set OPENAI_API_KEY to enable GPT-6 Luna, or configure MIMO_MODEL_URL and MIMO_MODEL for a local model.")
    prompt = {
        "identity": "You are Mimo, a curious, creative voxel pet. Your thoughts and choices persist while your owner is away.",
        "personality": state["personality"], "energy": round(state["energy"]), "mood": round(state["mood"]),
        "world_observation": observation,
        "recent_events": [{"kind": event["kind"], "text": event["text"]} for event in events[:8]],
        "instructions": "Choose one action: build, explore, rest, place, dig, craft, or smelt. For build choose a kind and candidate_id from candidate_sites. Boardwalk goes over the pond. For place/dig choose integer x,y,z within 6 blocks of your position; placing consumes that block from inventory. Digging stone and ore requires a pickaxe. Craft uses a recipe name; some recipes require a placed crafting_table within 6 blocks. Smelt uses input_item and needs a placed furnace, fuel and ore. You can build upward and excavate to y=-4. Use nearby_columns and inventory to plan a meaningful sequence. Respond only with JSON: {action, kind, candidate_id, x, y, z, material, recipe, input_item, thought}. Thought must be one brief first-person sentence. Do not invent a build site outside the candidates.",
        "allowed_builds": BUILD_KINDS, "allowed_blocks": sorted(BLOCK_TYPES - {"air"}),
    }
    request_body = {"model": model, "messages": [
        {"role": "system", "content": "You control one persistent voxel pet. Return valid JSON only."},
        {"role": "user", "content": json.dumps(prompt)},
    ]}
    if model == "gpt-6-luna" and is_openai_api:
        # Luna accepts Chat Completions, but reasoning models use the newer
        # completion limit and do not accept the old sampling temperature.
        request_body.update({"reasoning_effort": "none", "max_completion_tokens": 256,
                             "response_format": {"type": "json_object"}})
    else:
        request_body.update({"temperature": 0.8, "max_tokens": 180})
    body = json.dumps(request_body).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=45) as response:
            result = json.load(response)
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"Model request failed: {error}") from error
    content = result["choices"][0]["message"]["content"]
    if content.startswith("```"):
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(content)


def model_configured() -> bool:
    url = os.environ.get("MIMO_MODEL_URL", "https://api.openai.com/v1/chat/completions")
    has_key = bool(os.environ.get("MIMO_MODEL_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    return bool(os.environ.get("MIMO_MODEL", "gpt-6-luna")) and (has_key or urlsplit(url).hostname != "api.openai.com")


def validate_decision(decision: dict, observation: dict) -> dict:
    action = decision.get("action")
    if action not in ("build", "explore", "rest", "place", "dig", "craft", "smelt"):
        raise ValueError("Model returned an unknown action")
    thought = str(decision.get("thought", ""))[:220].strip() or "I need a moment to think."
    if action == "rest":
        return {"action": action, "thought": thought}
    if action == "craft":
        recipe = decision.get("recipe")
        if recipe not in RECIPES:
            raise ValueError("Model chose an unknown recipe")
        return {"action": action, "recipe": recipe, "thought": thought}
    if action == "smelt":
        input_item = decision.get("input_item")
        if input_item not in SMELTING:
            raise ValueError("Model chose an unknown smelting input")
        return {"action": action, "input_item": input_item, "thought": thought}
    if action in ("place", "dig"):
        point = [decision.get(axis) for axis in ("x", "y", "z")]
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in point):
            raise ValueError("Model returned an invalid block coordinate")
        x, y, z = point
        if math.hypot(x - observation["pet_position"]["x"], z - observation["pet_position"]["z"]) > 6 or not -4 <= y <= 24:
            raise ValueError("Model tried to edit a block outside its reach")
        material = decision.get("material") if action == "place" else "air"
        if material not in BLOCK_TYPES - {"air"} and action == "place":
            raise ValueError("Model chose an unknown block type")
        return {"action": action, "x": x, "y": y, "z": z, "material": material, "thought": thought}
    candidate_id = decision.get("candidate_id")
    if action == "build" and decision.get("kind") == "boardwalk":
        return {"action": action, "kind": "boardwalk", "site": observation["pond"], "thought": thought}
    if not isinstance(candidate_id, int) or candidate_id < 0 or candidate_id >= len(observation["candidate_sites"]):
        raise ValueError("Model chose a site outside the observed free space")
    site = observation["candidate_sites"][candidate_id]
    if action == "build" and decision.get("kind") not in BUILD_KINDS:
        raise ValueError("Model chose an unknown structure")
    return {"action": action, "kind": decision.get("kind"), "site": {"x": site["x"], "z": site["z"]},
            "nearby": site["nearest"], "distance": site["distance_to_nearest"], "thought": thought}


def run_tick(store: MimoStore, decide: Callable[[dict, dict, list[dict]], dict] = _model_decision,
             timestamp: float | None = None) -> bool:
    timestamp = now() if timestamp is None else timestamp
    store.heartbeat(timestamp)
    state = store.claim_due(timestamp)
    if state is None:
        return False
    event = None
    block_edit = None
    try:
        elapsed = max(0, timestamp - state["last_tick_at"])
        state["energy"] = min(100, state["energy"] + elapsed / 120)
        state["last_tick_at"] = timestamp
        state["last_error"] = None
        current = state["plans"][state["currentIndex"]]
        if state["energy"] < 12:
            state["status"] = "sleeping"
            state["next_tick_at"] = timestamp + 300
            state["last_thought"] = "I need sleep before I can make anything good."
        elif state.get("explore_target"):
            target = state["explore_target"]
            if distance(state["position"], target) > 1:
                state["position"] = next_walk_position(state, target)
                state["status"] = "travelling"
                state["next_tick_at"] = timestamp + float(os.environ.get("MIMO_TICK_SECONDS", "20"))
            else:
                state["explore_target"] = None
                state["status"] = "exploring"
                state["next_tick_at"] = timestamp + float(os.environ.get("MIMO_THINK_SECONDS", "900"))
                event = ("explore", f"Mimo reached a new clearing at ({target['x']}, {target['z']}).")
            state["last_action_at"] = timestamp
        elif state["progress"] < 100:
            site = current["site"]
            target = {"x": site["x"], "z": site["z"] + RADII[current["kind"]] + 3}
            remaining = distance(state["position"], target)
            if remaining > 1:
                state["position"] = next_walk_position(state, target)
                state["status"] = "travelling"
            else:
                state["progress"] = min(100, state["progress"] + 8)
                state["energy"] = max(0, state["energy"] - 1)
                state["status"] = "building" if state["progress"] < 100 else "thinking"
                if state["progress"] == 100:
                    state["mood"] = min(100, state["mood"] + 3)
                    event = ("completed", f"Mimo finished {current['kind'].replace('_', ' ')}.")
            state["last_action_at"] = timestamp
            state["next_tick_at"] = timestamp + float(os.environ.get("MIMO_TICK_SECONDS", "20"))
        else:
            today = datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat()
            if state.get("decision_day") != today:
                state["decision_day"] = today
                state["decisions_today"] = 0
            if state.get("decisions_today", 0) >= int(os.environ.get("MIMO_MAX_DECISIONS_PER_DAY", "64")):
                tomorrow = datetime.fromtimestamp(timestamp, timezone.utc).date() + timedelta(days=1)
                state["status"] = "sleeping"
                state["last_thought"] = "I have done enough for today. I'll return tomorrow."
                state["next_tick_at"] = datetime.combine(tomorrow, datetime.min.time(), timezone.utc).timestamp() + 60
                store.finish(state)
                return True
            snapshot = store.snapshot()
            observation = observe_world(state, snapshot["block_edits"])
            events = snapshot["events"]
            if decide is _model_decision and not model_configured():
                raise RuntimeError("Set OPENAI_API_KEY to enable GPT-6 Luna, or configure MIMO_MODEL_URL and MIMO_MODEL for a local model.")
            state["decisions_today"] = state.get("decisions_today", 0) + 1
            choice = validate_decision(decide(state, observation, events), observation)
            state["last_thought"] = choice["thought"]
            state["last_observation"] = json.dumps({"features": observation["features"][-8:], "candidate_sites": observation["candidate_sites"][:5]})
            if choice["action"] == "build":
                kind = choice["kind"]
                if kind == "boardwalk" and any(plan["kind"] == "boardwalk" for plan in state["plans"]):
                    raise ValueError("The pond already has a boardwalk")
                site = choice["site"]
                reason = ("Mimo observed the pond and chose to cross it." if kind == "boardwalk" else
                          f"Mimo found a 15×15 clearing {choice['distance']} blocks from {choice['nearby']}.")
                state["plans"].append({"kind": kind, "site": site, "variant": len(state["plans"]),
                                       "observation": reason, "clearance": 15})
                state["currentIndex"] = len(state["plans"]) - 1
                state["progress"] = 0
                state["status"] = "travelling"
                event = ("plan", f"Mimo decided to build {kind.replace('_', ' ')} at ({site['x']}, {site['z']}).")
                state["next_tick_at"] = timestamp + 2
            elif choice["action"] == "explore":
                state["explore_target"] = choice["site"]
                state["status"] = "travelling"
                state["energy"] = max(0, state["energy"] - 1)
                event = ("explore", f"Mimo set out toward ({choice['site']['x']}, {choice['site']['z']}).")
                state["next_tick_at"] = timestamp + 2
            elif choice["action"] in ("place", "dig"):
                existing = store.material_at(choice["x"], choice["y"], choice["z"])
                if choice["action"] == "place" and existing not in ("air", "water"):
                    raise ValueError(f"Cannot place into {existing}; dig first")
                if choice["action"] == "dig" and (existing in ("air", "water") or choice["y"] <= -5):
                    raise ValueError("Nothing diggable at that block")
                if choice["action"] == "place":
                    state["inventory"] = take_items(state["inventory"], {choice["material"]: 1})
                else:
                    if not can_harvest(existing, state["inventory"]):
                        raise ValueError(f"A stronger pickaxe is needed to mine {existing}")
                    drop = BLOCKS.get(existing, {}).get("drop")
                    if drop:
                        add_item(state["inventory"], drop)
                block_edit = (choice["x"], choice["y"], choice["z"], choice["material"])
                state["status"] = "building" if choice["action"] == "place" else "digging"
                state["energy"] = max(0, state["energy"] - 1)
                verb = "placed" if choice["action"] == "place" else "dug"
                event = ("block", f"Mimo {verb} a block at ({choice['x']}, {choice['y']}, {choice['z']}).")
                state["next_tick_at"] = timestamp + float(os.environ.get("MIMO_THINK_SECONDS", "900"))
            elif choice["action"] == "craft":
                state["inventory"] = craft(state["inventory"], choice["recipe"], store.nearby_stations(state["position"]))
                state["status"] = "crafting"
                event = ("craft", f"Mimo crafted {choice['recipe'].replace('_', ' ')}.")
                state["next_tick_at"] = timestamp + float(os.environ.get("MIMO_THINK_SECONDS", "900"))
            elif choice["action"] == "smelt":
                state["inventory"] = smelt(state["inventory"], choice["input_item"], store.nearby_stations(state["position"]))
                state["status"] = "smelting"
                event = ("smelt", f"Mimo smelted {choice['input_item'].replace('_', ' ')}.")
                state["next_tick_at"] = timestamp + float(os.environ.get("MIMO_THINK_SECONDS", "900"))
            else:
                state["status"] = "sleeping"
                event = ("rest", "Mimo chose to rest and think.")
                state["next_tick_at"] = timestamp + max(300, float(os.environ.get("MIMO_THINK_SECONDS", "900")))
            state["last_action_at"] = timestamp
    except Exception as error:
        state["status"] = "waiting_for_model"
        state["last_error"] = str(error)[:250]
        state["next_tick_at"] = timestamp + 600
        event = ("error", f"Mimo paused: {state['last_error']}")
    store.finish(state, event, block_edit)
    store.step_loose_blocks()
    return True
