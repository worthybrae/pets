"""World Map service — spatial index and build journal for pet worlds."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.services.db import insert_row, query_rows, upsert_row

logger = logging.getLogger(__name__)


class WorldMapService:
    """Manages world_regions and world_journal for a pet."""

    def __init__(self, pet_id: str):
        self.pet_id = pet_id

    # --- World Regions ---

    async def create_region(
        self,
        name: str,
        description: str,
        tags: list[str],
        bounds_min: tuple[int, int, int],
        bounds_max: tuple[int, int, int],
        relationships: dict[str, str] | None = None,
        status: str = "planned",
    ) -> str:
        """Create a new named region. Returns region ID."""
        region_id = str(uuid4())
        await insert_row("world_regions", {
            "id": region_id,
            "pet_id": self.pet_id,
            "name": name,
            "description": description,
            "tags": tags,
            "status": status,
            "bounds_min_x": bounds_min[0],
            "bounds_min_y": bounds_min[1],
            "bounds_min_z": bounds_min[2],
            "bounds_max_x": bounds_max[0],
            "bounds_max_y": bounds_max[1],
            "bounds_max_z": bounds_max[2],
            "relationships": relationships or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        return region_id

    async def get_all_regions(self) -> list[dict[str, Any]]:
        """Get all regions for this pet."""
        return await query_rows(
            "world_regions",
            {"pet_id": self.pet_id},
            limit=200,
            order_by="created_at",
            descending=False,
        )

    async def get_regions_near(
        self, x: int, y: int, z: int, radius: int = 50
    ) -> list[dict[str, Any]]:
        """Get regions whose bounding box overlaps a sphere around (x, y, z)."""
        all_regions = await self.get_all_regions()
        results = []
        for r in all_regions:
            closest_x = max(r["bounds_min_x"], min(x, r["bounds_max_x"]))
            closest_y = max(r["bounds_min_y"], min(y, r["bounds_max_y"]))
            closest_z = max(r["bounds_min_z"], min(z, r["bounds_max_z"]))
            dist_sq = (closest_x - x) ** 2 + (closest_y - y) ** 2 + (closest_z - z) ** 2
            if dist_sq <= radius ** 2:
                results.append(r)
        return results

    async def get_regions_by_status(self, status: str) -> list[dict[str, Any]]:
        """Get regions with a specific status."""
        return await query_rows(
            "world_regions",
            {"pet_id": self.pet_id, "status": status},
            limit=100,
        )

    async def update_region_status(self, region_id: str, status: str) -> None:
        """Update a region's status."""
        await upsert_row("world_regions", {
            "id": region_id,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    async def update_region(self, region_id: str, updates: dict[str, Any]) -> None:
        """Update arbitrary fields on a region."""
        updates["id"] = region_id
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await upsert_row("world_regions", updates)

    # --- World Journal ---

    async def add_journal_entry(
        self,
        creative_brief: str,
        build_plan: dict[str, Any],
        critic_review: dict[str, Any],
        region_id: str | None = None,
        voxels_placed: int = 0,
    ) -> str:
        """Add a build session journal entry. Returns entry ID."""
        entry_id = str(uuid4())
        await insert_row("world_journal", {
            "id": entry_id,
            "pet_id": self.pet_id,
            "creative_brief": creative_brief,
            "build_plan": build_plan,
            "critic_review": critic_review,
            "region_id": region_id,
            "voxels_placed": voxels_placed,
        })
        return entry_id

    async def get_recent_journal(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get the most recent journal entries."""
        return await query_rows(
            "world_journal",
            {"pet_id": self.pet_id},
            limit=limit,
            order_by="created_at",
            descending=True,
        )

    async def get_last_review(self) -> dict[str, Any] | None:
        """Get the critic review from the most recent journal entry."""
        entries = await self.get_recent_journal(limit=1)
        if entries and entries[0].get("critic_review"):
            return entries[0]["critic_review"]
        return None
