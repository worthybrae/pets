"""World persistence service — saves and loads voxel data to/from the database."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.services.db import insert_row, query_rows, upsert_row

logger = logging.getLogger(__name__)

# Chunk size must match frontend CHUNK_SIZE
CHUNK_SIZE = 16


def _voxel_to_chunk_key(x: int, y: int, z: int) -> tuple[int, int, int]:
    """Convert a world-space voxel position to its chunk coordinates."""
    return (x // CHUNK_SIZE, y // CHUNK_SIZE, z // CHUNK_SIZE)


async def save_pet_body(pet_id: str, voxels: list[dict[str, Any]]) -> None:
    """Persist the pet's body voxels (from define_self) to Supabase."""
    try:
        # Preserve existing position if present
        existing = await query_rows("pet_body", {"pet_id": pet_id}, limit=1)
        voxel_data: dict[str, Any] = {"voxels": voxels}
        if existing:
            old_data = existing[0].get("voxel_data", {})
            if "position" in old_data:
                voxel_data["position"] = old_data["position"]

        await upsert_row(
            "pet_body",
            {
                "pet_id": pet_id,
                "voxel_data": voxel_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="pet_id",
        )
    except Exception as e:
        logger.error(f"Failed to persist pet body for {pet_id}: {e}")


async def load_pet_body(pet_id: str) -> dict[str, Any] | None:
    """Load persisted body data (voxels + position) for a pet."""
    try:
        rows = await query_rows("pet_body", {"pet_id": pet_id}, limit=1)
        if rows:
            return rows[0].get("voxel_data", {})
    except Exception as e:
        logger.warning(f"Failed to load pet body for {pet_id}: {e}")
    return None


async def save_pet_position(pet_id: str, position: dict[str, float]) -> None:
    """Persist the pet's last AI-directed position."""
    try:
        existing = await query_rows("pet_body", {"pet_id": pet_id}, limit=1)
        if existing:
            voxel_data = existing[0].get("voxel_data", {})
            voxel_data["position"] = position
            await upsert_row(
                "pet_body",
                {
                    "pet_id": pet_id,
                    "voxel_data": voxel_data,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="pet_id",
            )
        else:
            await upsert_row(
                "pet_body",
                {
                    "pet_id": pet_id,
                    "voxel_data": {"position": position},
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="pet_id",
            )
    except Exception as e:
        logger.error(f"Failed to persist position for {pet_id}: {e}")


class WorldService:
    """Handles persistence of world voxel data for a pet."""

    def __init__(self, pet_id: str):
        self.pet_id = pet_id

    async def get_all_chunks(self) -> list[dict[str, Any]]:
        """Load all world chunks for this pet from the database."""
        try:
            rows = await query_rows(
                "world_chunks",
                {"pet_id": self.pet_id},
                limit=500,
            )
            return [
                {
                    "chunk_x": row["chunk_x"],
                    "chunk_y": row["chunk_y"],
                    "chunk_z": row["chunk_z"],
                    "voxels": row.get("voxel_data", {}).get("voxels", []),
                }
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to load world chunks for {self.pet_id}: {e}")
            return []

    async def place_voxels(self, voxels: list[dict[str, Any]]) -> int:
        """
        Persist placed voxels to the database.
        Groups voxels by chunk and upserts each chunk.
        Returns number of voxels persisted.
        """
        if not voxels:
            return 0

        # Group voxels by chunk
        chunks: dict[tuple[int, int, int], list[dict]] = {}
        for v in voxels:
            key = _voxel_to_chunk_key(v["x"], v["y"], v["z"])
            if key not in chunks:
                chunks[key] = []
            # Store voxel with chunk-local coordinates
            cx, cy, cz = key
            chunks[key].append({
                "x": v["x"] - cx * CHUNK_SIZE,
                "y": v["y"] - cy * CHUNK_SIZE,
                "z": v["z"] - cz * CHUNK_SIZE,
                "r": v["r"],
                "g": v["g"],
                "b": v["b"],
                "a": v.get("a", 255),
            })

        # Upsert each chunk
        count = 0
        for (cx, cy, cz), new_voxels in chunks.items():
            try:
                # Load existing chunk voxels
                existing = await query_rows(
                    "world_chunks",
                    {"pet_id": self.pet_id, "chunk_x": cx, "chunk_y": cy, "chunk_z": cz},
                    limit=1,
                )

                if existing:
                    # Append to existing voxels
                    row = existing[0]
                    current_voxels = row.get("voxel_data", {}).get("voxels", [])
                    merged = current_voxels + new_voxels
                    await upsert_row(
                        "world_chunks",
                        {
                            "id": row["id"],
                            "pet_id": self.pet_id,
                            "chunk_x": cx,
                            "chunk_y": cy,
                            "chunk_z": cz,
                            "voxel_data": {"voxels": merged},
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                else:
                    # Create new chunk
                    await insert_row(
                        "world_chunks",
                        {
                            "id": str(uuid4()),
                            "pet_id": self.pet_id,
                            "chunk_x": cx,
                            "chunk_y": cy,
                            "chunk_z": cz,
                            "voxel_data": {"voxels": new_voxels},
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                count += len(new_voxels)
            except Exception as e:
                logger.error(f"Failed to persist chunk ({cx},{cy},{cz}) for {self.pet_id}: {e}")

        return count

    async def remove_voxels(self, positions: list[dict[str, Any]]) -> int:
        """
        Remove voxels at given positions from the database.
        Returns number of voxels removed.
        """
        if not positions:
            return 0

        # Group positions by chunk
        chunks: dict[tuple[int, int, int], set[str]] = {}
        for p in positions:
            key = _voxel_to_chunk_key(p["x"], p["y"], p["z"])
            if key not in chunks:
                chunks[key] = set()
            cx, cy, cz = key
            local_key = f"{p['x'] - cx * CHUNK_SIZE},{p['y'] - cy * CHUNK_SIZE},{p['z'] - cz * CHUNK_SIZE}"
            chunks[key].add(local_key)

        count = 0
        for (cx, cy, cz), remove_keys in chunks.items():
            try:
                existing = await query_rows(
                    "world_chunks",
                    {"pet_id": self.pet_id, "chunk_x": cx, "chunk_y": cy, "chunk_z": cz},
                    limit=1,
                )
                if not existing:
                    continue

                row = existing[0]
                current_voxels = row.get("voxel_data", {}).get("voxels", [])
                filtered = [
                    v for v in current_voxels
                    if f"{v['x']},{v['y']},{v['z']}" not in remove_keys
                ]
                removed = len(current_voxels) - len(filtered)
                count += removed

                await upsert_row(
                    "world_chunks",
                    {
                        "id": row["id"],
                        "pet_id": self.pet_id,
                        "chunk_x": cx,
                        "chunk_y": cy,
                        "chunk_z": cz,
                        "voxel_data": {"voxels": filtered},
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to remove voxels from chunk ({cx},{cy},{cz}) for {self.pet_id}: {e}")

        return count

    async def seed_world(self, chunks: list[dict[str, Any]]) -> int:
        """
        Bulk-insert initial world chunks (called once to persist base world).
        Each chunk should have: chunk_x, chunk_y, chunk_z, voxels[].
        Idempotent — chunks that already exist are silently skipped.
        Returns total voxel count inserted.
        """
        total = 0
        for chunk in chunks:
            try:
                await insert_row(
                    "world_chunks",
                    {
                        "id": str(uuid4()),
                        "pet_id": self.pet_id,
                        "chunk_x": chunk["chunk_x"],
                        "chunk_y": chunk["chunk_y"],
                        "chunk_z": chunk["chunk_z"],
                        "voxel_data": {"voxels": chunk["voxels"]},
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                total += len(chunk["voxels"])
            except Exception as e:
                # Expected for chunks that already exist (unique index conflict)
                logger.debug(f"Chunk ({chunk['chunk_x']},{chunk['chunk_y']},{chunk['chunk_z']}) "
                             f"already exists for {self.pet_id}, skipping")
        return total
