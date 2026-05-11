"""Tests for WorldMapService."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from backend.services.world_map import WorldMapService


@pytest.fixture
def world_map(pet_id):
    return WorldMapService(pet_id)


@pytest.mark.asyncio
async def test_create_region(world_map, pet_id):
    with patch("backend.services.world_map.insert_row", new_callable=AsyncMock) as mock_insert:
        region_id = str(uuid4())
        mock_insert.return_value = {"id": region_id}

        result = await world_map.create_region(
            name="Terraced Garden",
            description="Overgrown hillside garden",
            tags=["garden", "overgrown"],
            bounds_min=(40, 0, 20),
            bounds_max=(70, 15, 50),
            relationships={"south_of": "cottage"},
        )

        assert result is not None
        mock_insert.assert_called_once()
        call_data = mock_insert.call_args[0][1]
        assert call_data["name"] == "Terraced Garden"
        assert call_data["bounds_min_x"] == 40
        assert call_data["bounds_max_z"] == 50


@pytest.mark.asyncio
async def test_get_regions_near(world_map, pet_id):
    with patch("backend.services.world_map.query_rows", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {
                "id": str(uuid4()), "name": "Cottage",
                "bounds_min_x": 10, "bounds_min_y": 0, "bounds_min_z": 10,
                "bounds_max_x": 20, "bounds_max_y": 8, "bounds_max_z": 20,
                "status": "complete", "tags": ["home"],
                "description": "A cozy cottage", "relationships": {},
            },
        ]
        regions = await world_map.get_regions_near(x=15, y=0, z=15, radius=30)
        assert len(regions) == 1
        assert regions[0]["name"] == "Cottage"


@pytest.mark.asyncio
async def test_update_region_status(world_map, pet_id):
    region_id = str(uuid4())
    with patch("backend.services.world_map.upsert_row", new_callable=AsyncMock) as mock_upsert:
        mock_upsert.return_value = {"id": region_id}
        await world_map.update_region_status(region_id, "complete")
        mock_upsert.assert_called_once()
        call_data = mock_upsert.call_args[0][1]
        assert call_data["status"] == "complete"


@pytest.mark.asyncio
async def test_add_journal_entry(world_map, pet_id):
    with patch("backend.services.world_map.insert_row", new_callable=AsyncMock) as mock_insert:
        mock_insert.return_value = {"id": str(uuid4())}
        entry_id = await world_map.add_journal_entry(
            creative_brief="Build a garden",
            build_plan={"project": "Garden"},
            critic_review={"overall_assessment": "Good"},
            region_id=str(uuid4()),
            voxels_placed=5000,
        )
        assert entry_id is not None


@pytest.mark.asyncio
async def test_get_recent_journal(world_map, pet_id):
    with patch("backend.services.world_map.query_rows", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {"id": str(uuid4()), "creative_brief": "Build tower",
             "critic_review": {"assessment": "good"}, "voxels_placed": 3000},
            {"id": str(uuid4()), "creative_brief": "Expand garden",
             "critic_review": {"assessment": "needs work"}, "voxels_placed": 1000},
        ]
        entries = await world_map.get_recent_journal(limit=5)
        assert len(entries) == 2
