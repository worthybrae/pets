# Studio Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic single-model AI loop with a four-stage Studio Pipeline (Dreamer → Architect → Builder → Critic) backed by persistent world map, world journal, and mood board systems — plus a voxel aesthetic overhaul for eggs and pets.

**Architecture:** Sequential pipeline where each stage reads shared context (soul, mood board, world map, journal) and produces a typed output for the next stage. Only the Builder modifies the world. All models are OpenAI (o4-mini for reasoning stages, GPT-4o for execution). New Supabase tables for world_regions, world_journal, and pet_mood_board. Frontend changes: voxel eggs, 0.25-unit pet voxels, hatching transition.

**Tech Stack:** Python/FastAPI, OpenAI API (o4-mini, GPT-4o, GPT-4o-mini), Supabase/PostgreSQL, React/Three.js (@react-three/fiber), Redis

---

## File Structure

### New Files (Backend)

```
backend/services/pipeline/
  __init__.py            # Package init, exports PipelineRunner
  runner.py              # Orchestrates Dreamer→Architect→Builder→Critic sequence
  dreamer.py             # Stage 1: creative ideation (o4-mini)
  architect.py           # Stage 2: spatial planning (o4-mini)
  builder.py             # Stage 3: voxel execution (GPT-4o)
  critic.py              # Stage 4: evaluation (o4-mini)
  context.py             # Loads shared context (soul, mood board, world map, journal)
  types.py               # Dataclasses: CreativeBrief, BuildPlan, BuildReport, CriticReview

backend/services/
  world_map.py           # WorldMapService: world_regions + world_journal CRUD + spatial queries
  mood_board.py          # MoodBoardService: theme extraction + CRUD + weight decay

backend/migrations/
  013_create_world_regions.sql
  014_create_world_journal.sql
  015_create_mood_board.sql

backend/tests/
  __init__.py
  test_world_map.py
  test_mood_board.py
  test_pipeline_types.py
  test_pipeline_runner.py
  conftest.py            # Shared fixtures (mock Supabase, mock OpenAI)
```

### New Files (Frontend)

```
frontend/src/components/hatch/
  VoxelEgg.tsx           # Voxel-based egg renderer (replaces shader egg)
  HatchTransition.tsx    # Voxel shatter → reform animation
```

### Modified Files

```
backend/services/brain.py        # Delegate autonomous_tick and birth to pipeline
backend/services/food.py         # Add o4-mini, o4 pricing
backend/api/websocket.py         # Add theme extraction after chat
frontend/src/components/world/PetEntity.tsx   # 0.25-unit voxels
frontend/src/components/hatch/EggScene.tsx     # Use VoxelEgg instead of shaders
frontend/src/components/hatch/Hatch.tsx        # Use HatchTransition
```

---

### Task 1: Database Migrations

**Files:**
- Create: `backend/migrations/013_create_world_regions.sql`
- Create: `backend/migrations/014_create_world_journal.sql`
- Create: `backend/migrations/015_create_mood_board.sql`
- Create: `supabase/migrations/20260510000000_create_world_regions.sql`
- Create: `supabase/migrations/20260510000001_create_world_journal.sql`
- Create: `supabase/migrations/20260510000002_create_mood_board.sql`

- [ ] **Step 1: Create world_regions migration**

```sql
-- backend/migrations/013_create_world_regions.sql
-- Semantic spatial index of named regions in a pet's world

create table if not exists world_regions (
  id uuid primary key default gen_random_uuid(),
  pet_id uuid not null references pets(id) on delete cascade,
  name text not null,
  description text,
  tags text[] default '{}',
  status text not null default 'planned'
    check (status in ('planned', 'in_progress', 'complete', 'needs_revision')),
  bounds_min_x int not null,
  bounds_min_y int not null,
  bounds_min_z int not null,
  bounds_max_x int not null,
  bounds_max_y int not null,
  bounds_max_z int not null,
  relationships jsonb default '{}',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index idx_world_regions_pet on world_regions(pet_id);
create index idx_world_regions_status on world_regions(pet_id, status);
```

Copy the same content to `supabase/migrations/20260510000000_create_world_regions.sql`.

- [ ] **Step 2: Create world_journal migration**

```sql
-- backend/migrations/014_create_world_journal.sql
-- Build session log — one entry per pipeline tick

create table if not exists world_journal (
  id uuid primary key default gen_random_uuid(),
  pet_id uuid not null references pets(id) on delete cascade,
  creative_brief text,
  build_plan jsonb,
  critic_review jsonb,
  region_id uuid references world_regions(id) on delete set null,
  voxels_placed int default 0,
  created_at timestamptz default now()
);

create index idx_world_journal_pet on world_journal(pet_id);
create index idx_world_journal_created on world_journal(pet_id, created_at desc);
```

Copy the same content to `supabase/migrations/20260510000001_create_world_journal.sql`.

- [ ] **Step 3: Create mood_board migration**

```sql
-- backend/migrations/015_create_mood_board.sql
-- Accumulated conversation themes that shape creative direction

create table if not exists pet_mood_board (
  id uuid primary key default gen_random_uuid(),
  pet_id uuid not null references pets(id) on delete cascade,
  theme text not null,
  weight float not null default 1.0,
  moments text[] default '{}',
  first_seen timestamptz default now(),
  last_seen timestamptz default now(),
  mention_count int default 1,
  unique(pet_id, theme)
);

create index idx_mood_board_pet on pet_mood_board(pet_id);
create index idx_mood_board_weight on pet_mood_board(pet_id, weight desc);
```

Copy the same content to `supabase/migrations/20260510000002_create_mood_board.sql`.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/013_create_world_regions.sql \
        backend/migrations/014_create_world_journal.sql \
        backend/migrations/015_create_mood_board.sql \
        supabase/migrations/20260510000000_create_world_regions.sql \
        supabase/migrations/20260510000001_create_world_journal.sql \
        supabase/migrations/20260510000002_create_mood_board.sql
git commit -m "feat: add migrations for world_regions, world_journal, pet_mood_board"
```

---

### Task 2: Pipeline Types

**Files:**
- Create: `backend/services/pipeline/__init__.py`
- Create: `backend/services/pipeline/types.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_pipeline_types.py`

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_pipeline_types.py
"""Tests for pipeline data types."""

from backend.services.pipeline.types import (
    CreativeBrief,
    BuildPlan,
    BuildPhase,
    BuildReport,
    CriticReview,
    ReviewIssue,
)


def test_creative_brief_from_text():
    brief = CreativeBrief(
        vision="Build a terraced garden on the eastern hillside",
        emotional_intent="Nostalgic, overgrown, alive",
        inspiration_source="Owner mentioned grandmother's garden",
    )
    assert "terraced garden" in brief.vision
    assert brief.inspiration_source is not None


def test_build_plan_total_operations():
    plan = BuildPlan(
        project="Test Tower",
        region_name="Tower Site",
        region_description="A tall stone tower",
        region_tags=["tower", "stone"],
        bounds={"min": [0, 0, 0], "max": [10, 30, 10]},
        phases=[
            BuildPhase(
                name="base",
                description="Stone foundation",
                operations=[
                    {"type": "fill_region", "x1": 0, "y1": 0, "z1": 0,
                     "x2": 10, "y2": 3, "z2": 10, "r": 128, "g": 128, "b": 128}
                ],
            ),
            BuildPhase(
                name="walls",
                description="Tower walls",
                operations=[
                    {"type": "place_cylinder", "cx": 5, "cz": 5,
                     "y_bottom": 3, "y_top": 25, "radius": 5,
                     "r": 160, "g": 160, "b": 160, "hollow": True}
                ],
            ),
        ],
        relationships={"north_of": "gate"},
    )
    assert len(plan.phases) == 2
    assert plan.total_operations() == 2
    assert plan.region_tags == ["tower", "stone"]


def test_build_report():
    report = BuildReport(
        voxels_placed=12500,
        phases_completed=["base", "walls"],
        phases_remaining=["roof"],
        errors=[],
    )
    assert report.voxels_placed == 12500
    assert report.success is True


def test_build_report_with_errors():
    report = BuildReport(
        voxels_placed=0,
        phases_completed=[],
        phases_remaining=["base"],
        errors=["Region too large"],
    )
    assert report.success is False


def test_critic_review():
    review = CriticReview(
        overall_assessment="Strong direction, needs detail",
        strengths=["good spatial placement"],
        issues=[
            ReviewIssue(
                area="walls",
                problem="too uniform",
                suggestion="add noise 20-30",
            )
        ],
        next_session_priorities=["wall texture"],
        region_status="in_progress",
    )
    assert len(review.issues) == 1
    assert review.region_status == "in_progress"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/worthy/TestCode/pets && python -m pytest backend/tests/test_pipeline_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.pipeline'`

- [ ] **Step 3: Create the package and types module**

```python
# backend/services/pipeline/__init__.py
"""Studio Pipeline — four-stage autonomous world-building AI."""

from backend.services.pipeline.types import (
    CreativeBrief,
    BuildPlan,
    BuildPhase,
    BuildReport,
    CriticReview,
    ReviewIssue,
)

__all__ = [
    "CreativeBrief",
    "BuildPlan",
    "BuildPhase",
    "BuildReport",
    "CriticReview",
    "ReviewIssue",
]
```

```python
# backend/services/pipeline/types.py
"""Data types passed between pipeline stages."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CreativeBrief:
    """Output of Stage 1 (Dreamer). Pure creative vision, no coordinates."""

    vision: str
    emotional_intent: str
    inspiration_source: str | None = None


@dataclass
class BuildPhase:
    """A single phase within a build plan."""

    name: str
    description: str
    operations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class BuildPlan:
    """Output of Stage 2 (Architect). Structured spatial plan."""

    project: str
    region_name: str
    region_description: str
    region_tags: list[str]
    bounds: dict[str, list[int]]  # {"min": [x,y,z], "max": [x,y,z]}
    phases: list[BuildPhase]
    relationships: dict[str, str] = field(default_factory=dict)

    def total_operations(self) -> int:
        return sum(len(p.operations) for p in self.phases)


@dataclass
class BuildReport:
    """Output of Stage 3 (Builder). What was actually placed."""

    voxels_placed: int
    phases_completed: list[str]
    phases_remaining: list[str]
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0 and self.voxels_placed > 0


@dataclass
class ReviewIssue:
    """A single issue identified by the Critic."""

    area: str
    problem: str
    suggestion: str


@dataclass
class CriticReview:
    """Output of Stage 4 (Critic). Evaluation of the build."""

    overall_assessment: str
    strengths: list[str]
    issues: list[ReviewIssue]
    next_session_priorities: list[str]
    region_status: str  # "in_progress" | "complete" | "needs_revision"
```

Also create `backend/tests/__init__.py` as an empty file.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/worthy/TestCode/pets && python -m pytest backend/tests/test_pipeline_types.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/pipeline/__init__.py \
        backend/services/pipeline/types.py \
        backend/tests/__init__.py \
        backend/tests/test_pipeline_types.py
git commit -m "feat: add pipeline data types (CreativeBrief, BuildPlan, BuildReport, CriticReview)"
```

---

### Task 3: World Map Service

**Files:**
- Create: `backend/services/world_map.py`
- Create: `backend/tests/test_world_map.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write the tests**

```python
# backend/tests/conftest.py
"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


@pytest.fixture
def mock_db():
    """Mock the database functions used by services."""
    with patch("backend.services.db.insert_row", new_callable=AsyncMock) as mock_insert, \
         patch("backend.services.db.query_rows", new_callable=AsyncMock) as mock_query, \
         patch("backend.services.db.upsert_row", new_callable=AsyncMock) as mock_upsert:
        mock_insert.return_value = {"id": str(uuid4())}
        mock_query.return_value = []
        mock_upsert.return_value = {"id": str(uuid4())}
        yield {
            "insert": mock_insert,
            "query": mock_query,
            "upsert": mock_upsert,
        }


@pytest.fixture
def pet_id():
    return str(uuid4())
```

```python
# backend/tests/test_world_map.py
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

        assert result == region_id
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
                "id": str(uuid4()),
                "name": "Cottage",
                "bounds_min_x": 10, "bounds_min_y": 0, "bounds_min_z": 10,
                "bounds_max_x": 20, "bounds_max_y": 8, "bounds_max_z": 20,
                "status": "complete",
                "tags": ["home"],
                "description": "A cozy cottage",
                "relationships": {},
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/worthy/TestCode/pets && python -m pytest backend/tests/test_world_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.world_map'`

- [ ] **Step 3: Implement WorldMapService**

```python
# backend/services/world_map.py
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
        """Get regions whose bounding box overlaps a sphere around (x, y, z).

        This loads all regions and filters in Python since Supabase
        doesn't support complex spatial queries without PostGIS.
        For the expected region count (<100 per pet), this is fine.
        """
        all_regions = await self.get_all_regions()
        results = []
        for r in all_regions:
            # Check if any corner of the bounding box is within radius
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/worthy/TestCode/pets && python -m pytest backend/tests/test_world_map.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/world_map.py \
        backend/tests/test_world_map.py \
        backend/tests/conftest.py
git commit -m "feat: add WorldMapService with regions and journal CRUD"
```

---

### Task 4: Mood Board Service

**Files:**
- Create: `backend/services/mood_board.py`
- Create: `backend/tests/test_mood_board.py`

- [ ] **Step 1: Write the tests**

```python
# backend/tests/test_mood_board.py
"""Tests for MoodBoardService."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from backend.services.mood_board import MoodBoardService


@pytest.fixture
def mood_board(pet_id):
    return MoodBoardService(pet_id)


@pytest.mark.asyncio
async def test_add_theme_new(mood_board, pet_id):
    """Adding a brand new theme creates a row with weight 1.0."""
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query, \
         patch("backend.services.mood_board.insert_row", new_callable=AsyncMock) as mock_insert:
        mock_query.return_value = []  # theme doesn't exist yet
        mock_insert.return_value = {"id": str(uuid4())}

        await mood_board.add_theme("ocean", moments=["wish I could sit by the ocean"])
        mock_insert.assert_called_once()
        call_data = mock_insert.call_args[0][1]
        assert call_data["theme"] == "ocean"
        assert call_data["weight"] == 1.0
        assert "wish I could sit by the ocean" in call_data["moments"]


@pytest.mark.asyncio
async def test_add_theme_existing_increments_weight(mood_board, pet_id):
    """Adding an existing theme increments weight and mention_count."""
    existing_id = str(uuid4())
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query, \
         patch("backend.services.mood_board.upsert_row", new_callable=AsyncMock) as mock_upsert:
        mock_query.return_value = [{
            "id": existing_id,
            "theme": "ocean",
            "weight": 3.0,
            "mention_count": 3,
            "moments": ["the sea is calming"],
        }]
        mock_upsert.return_value = {"id": existing_id}

        await mood_board.add_theme("ocean", moments=["I miss the beach"])
        mock_upsert.assert_called_once()
        call_data = mock_upsert.call_args[0][1]
        assert call_data["weight"] == 4.0
        assert call_data["mention_count"] == 4
        assert len(call_data["moments"]) == 2


@pytest.mark.asyncio
async def test_get_weighted_themes(mood_board, pet_id):
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = [
            {"theme": "ocean", "weight": 7.0, "moments": [], "mention_count": 7},
            {"theme": "nature", "weight": 3.0, "moments": [], "mention_count": 3},
            {"theme": "space", "weight": 0.5, "moments": [], "mention_count": 1},
        ]
        themes = await mood_board.get_weighted_themes()
        assert len(themes) == 3
        assert themes[0]["theme"] == "ocean"  # highest weight first


@pytest.mark.asyncio
async def test_extract_themes_from_messages(mood_board):
    """Theme extraction calls OpenAI and returns structured themes."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        '{"themes": [{"theme": "ocean", "relevance": 0.9, "moment": "wish I could sit by the ocean"},'
        '{"theme": "stress", "relevance": 0.6, "moment": null}]}'
    )
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    with patch("backend.services.mood_board.AsyncOpenAI") as MockClient:
        mock_client = AsyncMock()
        MockClient.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        themes = await mood_board.extract_themes([
            "I had a rough day, wish I could sit by the ocean"
        ])
        assert len(themes) == 2
        assert themes[0]["theme"] == "ocean"
        assert themes[0]["relevance"] == 0.9


@pytest.mark.asyncio
async def test_decay_weights(mood_board, pet_id):
    """Decay reduces weights but floors at 0.1."""
    old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    with patch("backend.services.mood_board.query_rows", new_callable=AsyncMock) as mock_query, \
         patch("backend.services.mood_board.upsert_row", new_callable=AsyncMock) as mock_upsert:
        mock_query.return_value = [
            {"id": str(uuid4()), "theme": "ocean", "weight": 2.0,
             "last_seen": old_date, "moments": [], "mention_count": 2},
            {"id": str(uuid4()), "theme": "fading", "weight": 0.3,
             "last_seen": old_date, "moments": [], "mention_count": 1},
        ]

        await mood_board.apply_decay(rate_per_day=0.1)

        # Should have been called twice (once per theme)
        assert mock_upsert.call_count == 2

        # Check the "fading" theme was clamped to 0.1
        calls = mock_upsert.call_args_list
        fading_call = [c for c in calls if c[0][1].get("id") == mock_query.return_value[1]["id"]]
        if fading_call:
            assert fading_call[0][0][1]["weight"] >= 0.1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/worthy/TestCode/pets && python -m pytest backend/tests/test_mood_board.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement MoodBoardService**

```python
# backend/services/mood_board.py
"""Mood Board service — tracks conversation themes that shape creative direction."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI

from backend.services.db import insert_row, query_rows, upsert_row

logger = logging.getLogger(__name__)

THEME_EXTRACTION_PROMPT = """Extract themes from this conversation between a pet owner and their pet.
Return a JSON object with a "themes" array. Each theme has:
- "theme": a single word or short phrase (lowercase)
- "relevance": 0.0-1.0 how strongly this theme appears
- "moment": a vivid specific quote worth remembering, or null

Focus on: emotions, imagery, topics, places, interests, relationships.
Only include themes with relevance >= 0.4.
Return at most 5 themes.

Respond with ONLY valid JSON, no markdown."""


class MoodBoardService:
    """Manages conversation theme extraction and the pet's mood board."""

    def __init__(self, pet_id: str):
        self.pet_id = pet_id

    # --- Theme Extraction ---

    async def extract_themes(self, messages: list[str]) -> list[dict[str, Any]]:
        """Extract themes from conversation messages using GPT-4o-mini.

        Returns list of {"theme": str, "relevance": float, "moment": str|None}.
        """
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        conversation_text = "\n".join(messages)

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": THEME_EXTRACTION_PROMPT},
                {"role": "user", "content": conversation_text},
            ],
            temperature=0.3,
        )

        content = response.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
            return data.get("themes", [])
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse theme extraction response: {content[:200]}")
            return []

    # --- Mood Board CRUD ---

    async def add_theme(
        self, theme: str, weight_increment: float = 1.0, moments: list[str] | None = None
    ) -> None:
        """Add or update a theme on the mood board."""
        existing = await query_rows(
            "pet_mood_board",
            {"pet_id": self.pet_id, "theme": theme},
            limit=1,
        )

        now = datetime.now(timezone.utc).isoformat()

        if existing:
            row = existing[0]
            old_moments = row.get("moments", []) or []
            new_moments = old_moments + (moments or [])
            # Keep at most 10 moments per theme
            new_moments = new_moments[-10:]

            await upsert_row("pet_mood_board", {
                "id": row["id"],
                "weight": row["weight"] + weight_increment,
                "mention_count": row["mention_count"] + 1,
                "moments": new_moments,
                "last_seen": now,
            })
        else:
            await insert_row("pet_mood_board", {
                "pet_id": self.pet_id,
                "theme": theme,
                "weight": weight_increment,
                "moments": moments or [],
                "mention_count": 1,
                "first_seen": now,
                "last_seen": now,
            })

    async def get_weighted_themes(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get themes sorted by weight (descending)."""
        return await query_rows(
            "pet_mood_board",
            {"pet_id": self.pet_id},
            limit=limit,
            order_by="weight",
            descending=True,
        )

    async def get_mood_board_summary(self) -> str:
        """Get a formatted summary of the mood board for the Dreamer prompt."""
        themes = await self.get_weighted_themes()
        if not themes:
            return "No conversation themes yet."

        lines = []
        for t in themes:
            weight = t["weight"]
            if weight > 5:
                strength = "STRONG"
            elif weight > 2:
                strength = "moderate"
            else:
                strength = "faint"

            line = f"- {t['theme']} ({strength}, weight {weight:.1f})"
            moments = t.get("moments", [])
            if moments:
                line += f" — \"{moments[-1]}\""
            lines.append(line)

        return "Your owner's recurring themes:\n" + "\n".join(lines)

    async def apply_decay(self, rate_per_day: float = 0.1) -> None:
        """Decay all theme weights based on time since last seen."""
        themes = await query_rows(
            "pet_mood_board",
            {"pet_id": self.pet_id},
            limit=200,
        )

        now = datetime.now(timezone.utc)
        for t in themes:
            last_seen = t.get("last_seen")
            if not last_seen:
                continue

            if isinstance(last_seen, str):
                last_dt = datetime.fromisoformat(last_seen)
            else:
                last_dt = last_seen

            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)

            days_since = (now - last_dt).total_seconds() / 86400
            decay = days_since * rate_per_day
            new_weight = max(0.1, t["weight"] - decay)

            if new_weight != t["weight"]:
                await upsert_row("pet_mood_board", {
                    "id": t["id"],
                    "weight": round(new_weight, 2),
                })

    # --- Process conversation ---

    async def process_conversation(self, messages: list[str]) -> int:
        """Extract themes from messages and update the mood board.

        Returns the number of themes added/updated.
        """
        themes = await self.extract_themes(messages)
        count = 0
        for t in themes:
            if t.get("relevance", 0) >= 0.4:
                moments = [t["moment"]] if t.get("moment") else []
                await self.add_theme(t["theme"], moments=moments)
                count += 1
        return count
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/worthy/TestCode/pets && python -m pytest backend/tests/test_mood_board.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/mood_board.py backend/tests/test_mood_board.py
git commit -m "feat: add MoodBoardService with theme extraction and weight decay"
```

---

### Task 5: Pipeline Context Loader

**Files:**
- Create: `backend/services/pipeline/context.py`

- [ ] **Step 1: Implement the context loader**

This module assembles all the shared state that pipeline stages need. No test file for this one — it's a thin glue layer over already-tested services.

```python
# backend/services/pipeline/context.py
"""Loads shared context for pipeline stages."""

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.services.memory import MemoryService
from backend.services.world_map import WorldMapService
from backend.services.mood_board import MoodBoardService
from backend.services.world import WorldService
from backend.services.agenda import get_current_agenda

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """All shared state available to pipeline stages."""

    pet_id: str
    pet_name: str
    pet_soul: str
    pet_stats: dict[str, Any]
    food_balance: float
    position: dict[str, float]

    # World awareness
    regions: list[dict[str, Any]] = field(default_factory=list)
    recent_journal: list[dict[str, Any]] = field(default_factory=list)
    last_review: dict[str, Any] | None = None

    # Mood board
    mood_board_summary: str = ""

    # Memory
    knowledge: list[dict[str, Any]] = field(default_factory=list)
    digested_notes: list[dict[str, Any]] = field(default_factory=list)

    # Agenda
    agenda_tasks: list[dict[str, Any]] = field(default_factory=list)
    current_task: dict[str, Any] | None = None


async def load_pipeline_context(pet_id: str, pet_state: dict[str, Any]) -> PipelineContext:
    """Load all context needed by pipeline stages from DB."""

    ctx = PipelineContext(
        pet_id=pet_id,
        pet_name=pet_state.get("name", "Pet"),
        pet_soul=pet_state.get("soul", ""),
        pet_stats=pet_state.get("stats", {}),
        food_balance=pet_state.get("food_balance", 0.0),
        position=pet_state.get("position", {"x": 0, "y": 0, "z": 0}),
    )

    # Load world map
    try:
        world_map = WorldMapService(pet_id)
        ctx.regions = await world_map.get_all_regions()
        ctx.recent_journal = await world_map.get_recent_journal(limit=5)
        ctx.last_review = await world_map.get_last_review()
    except Exception as e:
        logger.warning(f"Failed to load world map for {pet_id}: {e}")

    # Load mood board
    try:
        mood = MoodBoardService(pet_id)
        ctx.mood_board_summary = await mood.get_mood_board_summary()
    except Exception as e:
        logger.warning(f"Failed to load mood board for {pet_id}: {e}")

    # Load memory tiers
    try:
        memory = MemoryService(pet_id)
        ctx.knowledge = await memory.get_all_knowledge()
        ctx.digested_notes = await memory.get_recent_digests(limit=10)
    except Exception as e:
        logger.warning(f"Failed to load memory for {pet_id}: {e}")

    # Load agenda
    try:
        agenda_data = await get_current_agenda(pet_id)
        if agenda_data.get("status") != "no_agenda":
            ctx.agenda_tasks = agenda_data.get("tasks", [])
            ctx.current_task = agenda_data.get("current_task")
    except Exception as e:
        logger.warning(f"Failed to load agenda for {pet_id}: {e}")

    return ctx
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/pipeline/context.py
git commit -m "feat: add pipeline context loader"
```

---

### Task 6: Dreamer Stage

**Files:**
- Create: `backend/services/pipeline/dreamer.py`

- [ ] **Step 1: Implement the Dreamer**

```python
# backend/services/pipeline/dreamer.py
"""Stage 1: Dreamer — creative ideation using o4-mini."""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

from backend.services.pipeline.context import PipelineContext
from backend.services.pipeline.types import CreativeBrief

logger = logging.getLogger(__name__)


DREAMER_SYSTEM_PROMPT = """You are the creative mind of a pet named {name}. Your job is to decide what to build next in your voxel world.

=== Your Soul ===
{soul}

=== Your Stats ===
{stats}

=== Your World Map ===
{regions}

=== Recent Build Sessions ===
{journal}

=== Last Critic Review ===
{last_review}

=== Owner's Themes (Mood Board) ===
{mood_board}

=== Your Knowledge ===
{knowledge}

=== Instructions ===
You are the DREAMER. Your job is pure creative ideation. Decide WHAT to build and WHY.

Consider:
- What regions are in_progress or need_revision? Should you continue or start fresh?
- What themes from your owner's conversations could inspire your next build?
- How does this fit the overall vision of your world?
- What would delight your owner when they check in?

Do NOT include coordinates, voxel counts, or technical details. That's the Architect's job.

Respond with ONLY a JSON object:
{{
  "vision": "Describe what you want to build and why, in 2-4 sentences",
  "emotional_intent": "The feeling this build should evoke (1 sentence)",
  "inspiration_source": "What inspired this? Owner conversation, previous build, your personality, etc."
}}"""


async def run_dreamer(
    ctx: PipelineContext,
    model: str = "o4-mini",
    trigger: str = "autonomous_tick",
) -> tuple[CreativeBrief, Any]:
    """Run the Dreamer stage. Returns a CreativeBrief."""

    # Format regions for prompt
    if ctx.regions:
        region_lines = []
        for r in ctx.regions:
            region_lines.append(
                f"- {r['name']} [{r['status']}]: {r.get('description', 'no description')} "
                f"at ({r['bounds_min_x']},{r['bounds_min_y']},{r['bounds_min_z']}) to "
                f"({r['bounds_max_x']},{r['bounds_max_y']},{r['bounds_max_z']})"
            )
        regions_text = "\n".join(region_lines)
    else:
        regions_text = "Your world is empty. This is a blank canvas — build something extraordinary."

    # Format journal
    if ctx.recent_journal:
        journal_lines = []
        for j in ctx.recent_journal[:5]:
            brief = j.get("creative_brief", "no brief")
            voxels = j.get("voxels_placed", 0)
            journal_lines.append(f"- Built: {brief[:100]} ({voxels} voxels)")
        journal_text = "\n".join(journal_lines)
    else:
        journal_text = "No previous builds. This is your first session."

    # Format last review
    if ctx.last_review:
        review_text = json.dumps(ctx.last_review, indent=2)
    else:
        review_text = "No previous review."

    # Format knowledge
    if ctx.knowledge:
        knowledge_lines = [f"- {k.get('key', '?')}: {k.get('content', '')}" for k in ctx.knowledge[:15]]
        knowledge_text = "\n".join(knowledge_lines)
    else:
        knowledge_text = "No knowledge yet."

    # Format stats
    stats_text = ", ".join(f"{k}={v}" for k, v in ctx.pet_stats.items()) if ctx.pet_stats else "none"

    # Special first-build prompt
    if trigger == "birth":
        user_msg = (
            "You have just been born. Your world is an empty meadow. "
            "Dream of your first creation — something that will define who you are."
        )
    else:
        user_msg = "What do you want to build next? Dream big."

    system = DREAMER_SYSTEM_PROMPT.format(
        name=ctx.pet_name,
        soul=ctx.pet_soul or "No soul document yet.",
        stats=stats_text,
        regions=regions_text,
        journal=journal_text,
        last_review=review_text,
        mood_board=ctx.mood_board_summary or "No themes yet.",
        knowledge=knowledge_text,
    )

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {"vision": content, "emotional_intent": "unknown", "inspiration_source": "unknown"}

    return CreativeBrief(
        vision=data.get("vision", "Expand the world"),
        emotional_intent=data.get("emotional_intent", "wonder"),
        inspiration_source=data.get("inspiration_source"),
    ), response.usage
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/pipeline/dreamer.py
git commit -m "feat: add Dreamer stage (creative ideation with o4-mini)"
```

---

### Task 7: Architect Stage

**Files:**
- Create: `backend/services/pipeline/architect.py`

- [ ] **Step 1: Implement the Architect**

```python
# backend/services/pipeline/architect.py
"""Stage 2: Architect — spatial planning using o4-mini."""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

from backend.services.pipeline.context import PipelineContext
from backend.services.pipeline.types import BuildPlan, BuildPhase, CreativeBrief

logger = logging.getLogger(__name__)

ARCHITECT_SYSTEM_PROMPT = """You are the spatial planner for a voxel world. The Dreamer has decided what to build. Your job is to create a detailed build plan with coordinates, materials, and phases.

=== Available Build Tools ===
- fill_region: Rectangular box. Params: x1,y1,z1,x2,y2,z2,r,g,b,a,noise(0-60),hollow(bool),gradient_color({{r,g,b}})
- place_sphere: Sphere. Params: cx,cy,cz,radius(1-50),r,g,b,a,noise,hollow
- place_cylinder: Vertical cylinder. Params: cx,cz,y_bottom,y_top,radius(1-50),r,g,b,a,noise,hollow
- place_voxels: Individual voxels (max 5000). For fine detail only.
- execute_code: Python code that generates voxels procedurally. For complex organic shapes.

=== World Map (Existing Regions) ===
{regions}

=== Dreamer's Creative Brief ===
Vision: {vision}
Emotional intent: {emotional_intent}
Inspiration: {inspiration}

=== World Bounds ===
The base meadow is (-32,0,-32) to (47,0,47). Ground is at y=0. You can build anywhere — go beyond the meadow.
Pet is currently at ({px},{py},{pz}).

=== Instructions ===
Create a structured build plan. Place the build in a location that makes spatial sense relative to existing regions. Avoid overlapping existing structures.

Use noise for natural textures (10=smooth wood, 20=rough stone, 30=organic earth).
Use hollow=true for buildings with interiors.
Use gradient_color for walls that shift color.
Use execute_code operations for organic/procedural shapes (trees, terrain, fractals).

For execute_code operations, write the full Python code. The code must populate a `voxels` list with {{x,y,z,r,g,b,a}} dicts. You have access to `math`, `random`, `sin`, `cos`, `sqrt`, `pi`.

Respond with ONLY a JSON object:
{{
  "project": "name",
  "region_name": "name for the world map",
  "region_description": "what this region is",
  "region_tags": ["tag1", "tag2"],
  "bounds": {{"min": [x,y,z], "max": [x,y,z]}},
  "phases": [
    {{
      "name": "phase_name",
      "description": "what this phase builds",
      "operations": [
        {{"type": "fill_region", "x1": 0, ...}},
        {{"type": "execute_code", "code": "python code here"}}
      ]
    }}
  ],
  "relationships": {{"direction_of": "region_name"}}
}}"""


async def run_architect(
    ctx: PipelineContext,
    brief: CreativeBrief,
    model: str = "o4-mini",
) -> tuple[BuildPlan, Any]:
    """Run the Architect stage. Returns a BuildPlan and token usage."""

    # Format regions
    if ctx.regions:
        region_lines = []
        for r in ctx.regions:
            region_lines.append(
                f"- {r['name']} [{r['status']}] "
                f"({r['bounds_min_x']},{r['bounds_min_y']},{r['bounds_min_z']}) to "
                f"({r['bounds_max_x']},{r['bounds_max_y']},{r['bounds_max_z']})"
            )
        regions_text = "\n".join(region_lines)
    else:
        regions_text = "No existing regions. The world is empty."

    system = ARCHITECT_SYSTEM_PROMPT.format(
        regions=regions_text,
        vision=brief.vision,
        emotional_intent=brief.emotional_intent,
        inspiration=brief.inspiration_source or "N/A",
        px=int(ctx.position.get("x", 0)),
        py=int(ctx.position.get("y", 0)),
        pz=int(ctx.position.get("z", 0)),
    )

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Create the build plan for: {brief.vision}"},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.error(f"Architect returned invalid JSON: {content[:500]}")
        data = {
            "project": "Unknown", "region_name": "Unknown",
            "region_description": brief.vision, "region_tags": [],
            "bounds": {"min": [0, 0, 0], "max": [10, 10, 10]},
            "phases": [], "relationships": {},
        }

    phases = []
    for p in data.get("phases", []):
        phases.append(BuildPhase(
            name=p.get("name", "unnamed"),
            description=p.get("description", ""),
            operations=p.get("operations", []),
        ))

    plan = BuildPlan(
        project=data.get("project", "Unknown"),
        region_name=data.get("region_name", data.get("project", "Unknown")),
        region_description=data.get("region_description", brief.vision),
        region_tags=data.get("region_tags", []),
        bounds=data.get("bounds", {"min": [0, 0, 0], "max": [10, 10, 10]}),
        phases=phases,
        relationships=data.get("relationships", {}),
    )

    return plan, response.usage
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/pipeline/architect.py
git commit -m "feat: add Architect stage (spatial planning with o4-mini)"
```

---

### Task 8: Builder Stage

**Files:**
- Create: `backend/services/pipeline/builder.py`

- [ ] **Step 1: Implement the Builder**

The Builder is different from the other stages — it doesn't call OpenAI. It takes the Architect's structured build plan and executes the operations using the existing tool handlers from `tools.py`.

```python
# backend/services/pipeline/builder.py
"""Stage 3: Builder — executes build plans using existing tool handlers."""

import logging
from typing import Any

from backend.services.pipeline.types import BuildPlan, BuildReport
from backend.services.tools import execute_tool
from backend.services.events import get_broadcaster

logger = logging.getLogger(__name__)


async def run_builder(
    pet_id: str,
    plan: BuildPlan,
) -> BuildReport:
    """Execute a build plan phase by phase. Returns a BuildReport."""

    total_voxels = 0
    completed_phases: list[str] = []
    remaining_phases: list[str] = []
    errors: list[str] = []

    broadcaster = get_broadcaster()

    for i, phase in enumerate(plan.phases):
        if broadcaster:
            await broadcaster.pet_thought(
                pet_id,
                f"Building: {phase.name} — {phase.description}",
                "pipeline_builder",
            )

        phase_voxels = 0
        phase_errors = []

        for op in phase.operations:
            op_type = op.get("type", "")

            # Map operation to tool call
            if op_type in ("fill_region", "place_sphere", "place_cylinder",
                           "place_voxels", "remove_voxels", "execute_code"):
                # Build the args dict (exclude "type" key)
                args = {k: v for k, v in op.items() if k != "type"}
                result = await execute_tool(pet_id, op_type, args)

                if result.get("success"):
                    placed = result.get("placed", 0) or result.get("voxels_generated", 0)
                    phase_voxels += placed
                else:
                    error_msg = result.get("error", "unknown error")
                    phase_errors.append(f"{phase.name}/{op_type}: {error_msg}")
                    logger.warning(f"Builder op failed: {op_type} in {phase.name}: {error_msg}")
            else:
                phase_errors.append(f"Unknown operation type: {op_type}")

        total_voxels += phase_voxels

        if phase_errors:
            errors.extend(phase_errors)
            # Still mark as completed if some ops succeeded
            if phase_voxels > 0:
                completed_phases.append(phase.name)
            else:
                remaining_phases.append(phase.name)
        else:
            completed_phases.append(phase.name)

        logger.info(f"Phase '{phase.name}' complete: {phase_voxels} voxels placed")

    return BuildReport(
        voxels_placed=total_voxels,
        phases_completed=completed_phases,
        phases_remaining=remaining_phases,
        errors=errors,
    )
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/pipeline/builder.py
git commit -m "feat: add Builder stage (executes build plans via tool handlers)"
```

---

### Task 9: Critic Stage

**Files:**
- Create: `backend/services/pipeline/critic.py`

- [ ] **Step 1: Implement the Critic**

```python
# backend/services/pipeline/critic.py
"""Stage 4: Critic — evaluates builds using o4-mini."""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

from backend.services.pipeline.context import PipelineContext
from backend.services.pipeline.types import (
    BuildPlan,
    BuildReport,
    CreativeBrief,
    CriticReview,
    ReviewIssue,
)

logger = logging.getLogger(__name__)

CRITIC_SYSTEM_PROMPT = """You are the quality critic for a pet's voxel world builds. You evaluate what was built against the original creative vision.

=== Creative Brief (Original Intent) ===
Vision: {vision}
Emotional intent: {emotional_intent}

=== Build Plan ===
Project: {project}
Phases planned: {phases_planned}

=== Build Results ===
Voxels placed: {voxels_placed}
Phases completed: {phases_completed}
Phases remaining: {phases_remaining}
Errors: {errors}

=== Recent World Context ===
{journal}

=== Instructions ===
Evaluate this build session. Consider:
- Did the build match the creative brief's vision and emotional intent?
- What worked well? What structures or details are effective?
- What needs improvement? (texture variation, density, scale, spatial coherence)
- What should the next session focus on?
- Should this region be marked as "complete", "in_progress", or "needs_revision"?

Be specific and constructive. Reference particular aspects of the build.

Respond with ONLY a JSON object:
{{
  "overall_assessment": "1-2 sentence summary",
  "strengths": ["strength 1", "strength 2"],
  "issues": [
    {{"area": "what part", "problem": "what's wrong", "suggestion": "how to fix"}}
  ],
  "next_session_priorities": ["priority 1", "priority 2"],
  "region_status": "in_progress|complete|needs_revision"
}}"""


async def run_critic(
    ctx: PipelineContext,
    brief: CreativeBrief,
    plan: BuildPlan,
    report: BuildReport,
    model: str = "o4-mini",
) -> tuple[CriticReview, Any]:
    """Run the Critic stage. Returns a CriticReview and token usage."""

    # Format journal context
    if ctx.recent_journal:
        journal_lines = [
            f"- {j.get('creative_brief', '?')[:80]} ({j.get('voxels_placed', 0)} voxels)"
            for j in ctx.recent_journal[:3]
        ]
        journal_text = "\n".join(journal_lines)
    else:
        journal_text = "This is the first build session."

    phases_planned = ", ".join(p.name for p in plan.phases)

    system = CRITIC_SYSTEM_PROMPT.format(
        vision=brief.vision,
        emotional_intent=brief.emotional_intent,
        project=plan.project,
        phases_planned=phases_planned,
        voxels_placed=report.voxels_placed,
        phases_completed=", ".join(report.phases_completed) or "none",
        phases_remaining=", ".join(report.phases_remaining) or "none",
        errors="; ".join(report.errors) if report.errors else "none",
        journal=journal_text,
    )

    client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "Evaluate this build session."},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = {
            "overall_assessment": "Unable to evaluate",
            "strengths": [],
            "issues": [],
            "next_session_priorities": [],
            "region_status": "in_progress",
        }

    issues = []
    for issue_data in data.get("issues", []):
        issues.append(ReviewIssue(
            area=issue_data.get("area", "unknown"),
            problem=issue_data.get("problem", "unknown"),
            suggestion=issue_data.get("suggestion", ""),
        ))

    review = CriticReview(
        overall_assessment=data.get("overall_assessment", "No assessment"),
        strengths=data.get("strengths", []),
        issues=issues,
        next_session_priorities=data.get("next_session_priorities", []),
        region_status=data.get("region_status", "in_progress"),
    )

    return review, response.usage
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/pipeline/critic.py
git commit -m "feat: add Critic stage (build evaluation with o4-mini)"
```

---

### Task 10: Pipeline Runner

**Files:**
- Create: `backend/services/pipeline/runner.py`

- [ ] **Step 1: Implement the Pipeline Runner**

```python
# backend/services/pipeline/runner.py
"""Pipeline Runner — orchestrates Dreamer → Architect → Builder → Critic."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.services.pipeline.context import PipelineContext, load_pipeline_context
from backend.services.pipeline.dreamer import run_dreamer
from backend.services.pipeline.architect import run_architect
from backend.services.pipeline.builder import run_builder
from backend.services.pipeline.critic import run_critic
from backend.services.pipeline.types import (
    BuildPlan,
    BuildReport,
    CreativeBrief,
    CriticReview,
)
from backend.services.world_map import WorldMapService
from backend.services.food import check_food, deduct_llm_cost
from backend.services.events import get_broadcaster

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    brief: CreativeBrief | None = None
    plan: BuildPlan | None = None
    report: BuildReport | None = None
    review: CriticReview | None = None
    total_food_consumed: float = 0.0
    error: str | None = None


class PipelineRunner:
    """Orchestrates the four-stage Studio Pipeline."""

    def __init__(
        self,
        pet_id: str,
        pet_state: dict[str, Any],
        dreamer_model: str = "o4-mini",
        architect_model: str = "o4-mini",
        critic_model: str = "o4-mini",
    ):
        self.pet_id = pet_id
        self.pet_state = pet_state
        self.dreamer_model = dreamer_model
        self.architect_model = architect_model
        self.critic_model = critic_model

    async def run(self, trigger: str = "autonomous_tick") -> PipelineResult:
        """Run the full pipeline: Dreamer → Architect → Builder → Critic."""

        result = PipelineResult()
        broadcaster = get_broadcaster()

        # Check food
        food = await check_food(self.pet_id)
        if food <= 0:
            result.error = "No food remaining."
            return result

        # Load shared context
        ctx = await load_pipeline_context(self.pet_id, self.pet_state)

        # --- Stage 1: Dreamer ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Dreaming...", "pipeline_dreamer")

        try:
            brief, dreamer_usage = await run_dreamer(ctx, model=self.dreamer_model, trigger=trigger)
            result.brief = brief
            if dreamer_usage:
                ok, cost = await deduct_llm_cost(
                    self.pet_id, self.dreamer_model,
                    dreamer_usage.prompt_tokens, dreamer_usage.completion_tokens,
                )
                if not ok:
                    result.error = "Insufficient food for Dreamer."
                    return result
                result.total_food_consumed += cost
            logger.info(f"Dreamer: {brief.vision[:100]}")
        except Exception as e:
            logger.error(f"Dreamer failed for {self.pet_id}: {e}")
            result.error = f"Dreamer failed: {e}"
            return result

        # --- Stage 2: Architect ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Planning the build...", "pipeline_architect")

        try:
            plan, architect_usage = await run_architect(ctx, brief, model=self.architect_model)
            result.plan = plan
            if architect_usage:
                ok, cost = await deduct_llm_cost(
                    self.pet_id, self.architect_model,
                    architect_usage.prompt_tokens, architect_usage.completion_tokens,
                )
                if not ok:
                    result.error = "Insufficient food for Architect."
                    return result
                result.total_food_consumed += cost
            logger.info(f"Architect: {plan.project} — {len(plan.phases)} phases")
        except Exception as e:
            logger.error(f"Architect failed for {self.pet_id}: {e}")
            result.error = f"Architect failed: {e}"
            return result

        # Register region in world map
        world_map = WorldMapService(self.pet_id)
        try:
            bounds_min = plan.bounds.get("min", [0, 0, 0])
            bounds_max = plan.bounds.get("max", [10, 10, 10])
            region_id = await world_map.create_region(
                name=plan.region_name,
                description=plan.region_description,
                tags=plan.region_tags,
                bounds_min=tuple(bounds_min),
                bounds_max=tuple(bounds_max),
                relationships=plan.relationships,
                status="in_progress",
            )
        except Exception as e:
            logger.warning(f"Failed to register region: {e}")
            region_id = None

        # --- Stage 3: Builder ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Building...", "pipeline_builder")

        try:
            report = await run_builder(self.pet_id, plan)
            result.report = report
            logger.info(f"Builder: {report.voxels_placed} voxels placed, "
                        f"{len(report.phases_completed)} phases complete")
        except Exception as e:
            logger.error(f"Builder failed for {self.pet_id}: {e}")
            result.error = f"Builder failed: {e}"
            return result

        # --- Stage 4: Critic ---
        if broadcaster:
            await broadcaster.pet_thought(self.pet_id, "Evaluating the build...", "pipeline_critic")

        try:
            review, critic_usage = await run_critic(
                ctx, brief, plan, report, model=self.critic_model,
            )
            result.review = review
            if critic_usage:
                ok, cost = await deduct_llm_cost(
                    self.pet_id, self.critic_model,
                    critic_usage.prompt_tokens, critic_usage.completion_tokens,
                )
                if not ok:
                    result.error = "Insufficient food for Critic (build was still placed)."
                result.total_food_consumed += cost
            logger.info(f"Critic: {review.overall_assessment}")
        except Exception as e:
            logger.error(f"Critic failed for {self.pet_id}: {e}")
            # Non-fatal: the build was already placed
            review = None

        # --- Persist Results ---

        # Update region status from critic
        if region_id and review:
            try:
                await world_map.update_region_status(region_id, review.region_status)
            except Exception as e:
                logger.warning(f"Failed to update region status: {e}")

        # Write journal entry
        try:
            await world_map.add_journal_entry(
                creative_brief=brief.vision,
                build_plan={
                    "project": plan.project,
                    "phases": [{"name": p.name, "description": p.description} for p in plan.phases],
                },
                critic_review={
                    "overall_assessment": review.overall_assessment,
                    "strengths": review.strengths,
                    "issues": [{"area": i.area, "problem": i.problem, "suggestion": i.suggestion}
                               for i in review.issues],
                    "next_session_priorities": review.next_session_priorities,
                } if review else {"overall_assessment": "No review (critic failed)"},
                region_id=region_id,
                voxels_placed=report.voxels_placed,
            )
        except Exception as e:
            logger.warning(f"Failed to write journal entry: {e}")

        # Broadcast food update
        remaining_food = await check_food(self.pet_id)
        if broadcaster:
            await broadcaster.food_updated(self.pet_id, remaining_food)

        return result
```

- [ ] **Step 2: Update `__init__.py` to export PipelineRunner**

Add to `backend/services/pipeline/__init__.py`:

```python
from backend.services.pipeline.runner import PipelineRunner, PipelineResult
```

And add `"PipelineRunner"` and `"PipelineResult"` to `__all__`.

- [ ] **Step 3: Commit**

```bash
git add backend/services/pipeline/runner.py backend/services/pipeline/__init__.py
git commit -m "feat: add PipelineRunner orchestrating Dreamer→Architect→Builder→Critic"
```

---

### Task 11: Update Food Pricing

**Files:**
- Modify: `backend/services/food.py`

- [ ] **Step 1: Add o4-mini and o4 pricing**

Add the following entries to `MODEL_PRICING` in `backend/services/food.py`:

```python
    "o4-mini": {
        "input": 1.10 / 1_000_000,   # $1.10 per 1M input tokens
        "output": 4.40 / 1_000_000,   # $4.40 per 1M output tokens
    },
    "o4": {
        "input": 10.00 / 1_000_000,
        "output": 40.00 / 1_000_000,
    },
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/food.py
git commit -m "feat: add o4-mini and o4 pricing to food system"
```

---

### Task 12: Integrate Pipeline into brain.py

**Files:**
- Modify: `backend/services/brain.py`

- [ ] **Step 1: Add pipeline delegation for autonomous_tick and birth triggers**

At the top of `brain.py`, add the import:

```python
from backend.services.pipeline.runner import PipelineRunner, PipelineResult
```

Add a new method to `PetBrain` class, before the `think()` method:

```python
    async def _run_pipeline(self, trigger: str, context: dict[str, Any]) -> BrainResult:
        """Delegate to the Studio Pipeline for autonomous ticks and birth."""
        result = BrainResult()

        runner = PipelineRunner(
            pet_id=self.pet_id,
            pet_state=self.pet_state,
            dreamer_model="o4-mini",
            architect_model="o4-mini",
            critic_model="o4-mini",
        )

        pipeline_result = await runner.run(trigger=trigger)

        result.food_consumed = pipeline_result.total_food_consumed

        if pipeline_result.error:
            result.error = pipeline_result.error

        if pipeline_result.report:
            result.actions.append({
                "tool": "pipeline",
                "args": {"trigger": trigger},
                "result": {
                    "voxels_placed": pipeline_result.report.voxels_placed,
                    "phases_completed": pipeline_result.report.phases_completed,
                },
            })

        return result
```

Then modify the `think()` method to delegate autonomous_tick and birth:

In the `think()` method, right after the food check block (`if food <= 0: ...`), add:

```python
        # Delegate autonomous ticks and birth to the Studio Pipeline
        if trigger in ("autonomous_tick", "birth"):
            pipeline_result = await self._run_pipeline(trigger, context)
            await self._log_interaction(trigger, context, pipeline_result)
            return pipeline_result
```

This goes before `await self._load_memory_into_state()`.

- [ ] **Step 2: Commit**

```bash
git add backend/services/brain.py
git commit -m "feat: delegate autonomous_tick and birth to Studio Pipeline"
```

---

### Task 13: Add Theme Extraction to Chat Flow

**Files:**
- Modify: `backend/api/websocket.py`

- [ ] **Step 1: Add theme extraction after chat processing**

At the top of `websocket.py`, add:

```python
from backend.services.mood_board import MoodBoardService
```

In the `_process_chat` function, after the line `await broadcaster.food_updated(pet_id, remaining_food)` (around line 223), add:

```python
        # Extract themes from conversation for mood board (fire-and-forget)
        try:
            mood = MoodBoardService(pet_id)
            await mood.process_conversation([user_message])
        except Exception as e:
            logger.warning(f"Theme extraction failed for {pet_id}: {e}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/api/websocket.py
git commit -m "feat: extract conversation themes into mood board after chat"
```

---

### Task 14: Voxel Egg Renderer

**Files:**
- Create: `frontend/src/components/hatch/VoxelEgg.tsx`

- [ ] **Step 1: Implement VoxelEgg component**

This replaces the shader-based egg with an instanced mesh voxel egg. It generates an egg silhouette from small cubes (0.5 unit), applies the color palette and scale patterns as voxel textures.

```tsx
// frontend/src/components/hatch/VoxelEgg.tsx
import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

const VOXEL_SIZE = 0.5

interface VoxelEggProps {
  color: { base: [number, number, number]; core: [number, number, number] }
  shape: number // 0-7 maps to egg shape
  size: number // scale multiplier
  scale_pattern: number // 0-7 surface texture pattern
}

function generateEggVoxels(
  shape: number,
  size: number,
  scalePattern: number,
  baseColor: [number, number, number],
  coreColor: [number, number, number],
): { positions: Float32Array; colors: Float32Array; count: number } {
  const voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[] = []

  // Egg dimensions based on shape
  const heightMap: Record<number, { h: number; w: number }> = {
    0: { h: 8, w: 5 },    // Round
    1: { h: 10, w: 4.5 },  // Oval
    2: { h: 7, w: 5.5 },   // Squat
    3: { h: 12, w: 4 },    // Elongated
    4: { h: 10, w: 4.5 },  // Teardrop
    5: { h: 8, w: 5.5 },   // Bulbous
    6: { h: 10, w: 4 },    // Gourd
    7: { h: 13, w: 3.5 },  // Spire
  }

  const { h, w } = heightMap[shape] || heightMap[0]
  const height = Math.round(h * size)
  const width = Math.round(w * size)

  // Generate egg shape using ellipsoid with shape-specific deformation
  for (let y = -height; y <= height; y++) {
    // Radius at this height (egg profile)
    const t = (y + height) / (2 * height) // 0 at bottom, 1 at top
    // Egg shape: wider at bottom, narrower at top
    const profileR = Math.sin(t * Math.PI) * width * (1 - 0.3 * (t - 0.5))

    for (let x = -width; x <= width; x++) {
      for (let z = -width; z <= width; z++) {
        const dist = Math.sqrt(x * x + z * z)
        if (dist <= profileR && dist > profileR - 1) {
          // Surface voxel — apply scale pattern for color
          const isPattern = applyScalePattern(x, y, z, scalePattern)
          const [r, g, b] = isPattern ? coreColor : baseColor

          voxels.push({ x, y, z, r, g, b })
        }
      }
    }
  }

  const positions = new Float32Array(voxels.length * 3)
  const colors = new Float32Array(voxels.length * 3)

  voxels.forEach((v, i) => {
    positions[i * 3] = v.x * VOXEL_SIZE
    positions[i * 3 + 1] = v.y * VOXEL_SIZE
    positions[i * 3 + 2] = v.z * VOXEL_SIZE
    colors[i * 3] = v.r / 255
    colors[i * 3 + 1] = v.g / 255
    colors[i * 3 + 2] = v.b / 255
  })

  return { positions, colors, count: voxels.length }
}

function applyScalePattern(x: number, y: number, z: number, pattern: number): boolean {
  switch (pattern) {
    case 0: return false // None
    case 1: return (x + y + z) % 3 === 0 // Speckled
    case 2: return y % 3 === 0 // Horizontal stripes
    case 3: return (x + z) % 4 === 0 // Vertical stripes
    case 4: return (Math.abs(x) + Math.abs(z)) % 5 < 2 // Diamond
    case 5: return Math.sin(y * 0.5 + Math.atan2(z, x) * 2) > 0.3 // Spiral
    case 6: return (x * x + z * z + y) % 7 < 2 // Scattered
    case 7: return (x + y) % 2 === 0 && (y + z) % 2 === 0 // Checker
    default: return false
  }
}

export default function VoxelEgg({ color, shape, size, scale_pattern }: VoxelEggProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)

  const { positions, colors, count } = useMemo(
    () => generateEggVoxels(shape, size, scale_pattern, color.base, color.core),
    [shape, size, scale_pattern, color.base, color.core],
  )

  // Set up instanced mesh transforms
  useMemo(() => {
    if (!meshRef.current || count === 0) return
    const mesh = meshRef.current
    const matrix = new THREE.Matrix4()

    for (let i = 0; i < count; i++) {
      matrix.setPosition(
        positions[i * 3],
        positions[i * 3 + 1],
        positions[i * 3 + 2],
      )
      mesh.setMatrixAt(i, matrix)
      mesh.setColorAt(
        i,
        new THREE.Color().setRGB(
          colors[i * 3],
          colors[i * 3 + 1],
          colors[i * 3 + 2],
          THREE.SRGBColorSpace,
        ),
      )
    }
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [positions, colors, count])

  // Gentle bob animation
  const groupRef = useRef<THREE.Group>(null)
  useFrame((_, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.2
    }
  })

  if (count === 0) return null

  return (
    <group ref={groupRef}>
      <instancedMesh ref={meshRef} args={[undefined, undefined, count]}>
        <boxGeometry args={[VOXEL_SIZE, VOXEL_SIZE, VOXEL_SIZE]} />
        <meshStandardMaterial roughness={0.4} metalness={0.1} />
      </instancedMesh>
    </group>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/hatch/VoxelEgg.tsx
git commit -m "feat: add VoxelEgg component (voxel-based egg renderer)"
```

---

### Task 15: Higher-Fidelity Pet Bodies

**Files:**
- Modify: `frontend/src/components/world/PetEntity.tsx`

- [ ] **Step 1: Change pet voxel size to 0.25 units**

In `PetEntity.tsx`, find the boxGeometry for the pet body instanced mesh. Change the voxel size from `1` to `0.25`:

Find the line where the pet body boxGeometry is created (should be something like `<boxGeometry args={[1, 1, 1]} />`).

Change it to:

```tsx
<boxGeometry args={[0.25, 0.25, 0.25]} />
```

Also update the matrix position calculation for each voxel instance. Where it does:

```tsx
matrix.setPosition(v.x, v.y, v.z)
```

Change to:

```tsx
matrix.setPosition(v.x * 0.25, v.y * 0.25, v.z * 0.25)
```

This makes pet bodies 4x higher resolution while keeping them the same physical size in the world (assuming the AI generates body voxels at the same coordinate scale — the `define_self` tool still uses integer coordinates, they just map to quarter-unit cubes).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/world/PetEntity.tsx
git commit -m "feat: use 0.25-unit voxels for pet bodies (higher fidelity)"
```

---

### Task 16: Hatching Transition

**Files:**
- Create: `frontend/src/components/hatch/HatchTransition.tsx`

- [ ] **Step 1: Implement the voxel shatter/reform animation**

```tsx
// frontend/src/components/hatch/HatchTransition.tsx
import { useRef, useMemo, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

interface HatchTransitionProps {
  eggVoxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  petVoxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  phase: 'idle' | 'shatter' | 'reform' | 'complete'
  onComplete: () => void
}

const VOXEL_SIZE = 0.25
const SHATTER_DURATION = 1.5 // seconds
const REFORM_DURATION = 2.0

export default function HatchTransition({
  eggVoxels,
  petVoxels,
  phase,
  onComplete,
}: HatchTransitionProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const progressRef = useRef(0)
  const [currentPhase, setCurrentPhase] = useState(phase)

  // Max count is the larger of egg or pet voxels
  const maxCount = Math.max(eggVoxels.length, petVoxels.length)

  // Precompute random scatter directions for shatter effect
  const scatterDirs = useMemo(() => {
    return Array.from({ length: maxCount }, () => ({
      x: (Math.random() - 0.5) * 10,
      y: Math.random() * 8 + 2,
      z: (Math.random() - 0.5) * 10,
    }))
  }, [maxCount])

  useFrame((_, delta) => {
    if (!meshRef.current || currentPhase === 'idle' || currentPhase === 'complete') return

    const mesh = meshRef.current
    const matrix = new THREE.Matrix4()
    const color = new THREE.Color()

    if (currentPhase === 'shatter') {
      progressRef.current += delta / SHATTER_DURATION
      const t = Math.min(progressRef.current, 1)

      // Egg voxels scatter outward
      for (let i = 0; i < eggVoxels.length; i++) {
        const v = eggVoxels[i]
        const scatter = scatterDirs[i]
        const ease = t * t // accelerating

        matrix.setPosition(
          (v.x * 0.5 + scatter.x * ease) * VOXEL_SIZE,
          (v.y * 0.5 + scatter.y * ease - 5 * ease * ease) * VOXEL_SIZE,
          (v.z * 0.5 + scatter.z * ease) * VOXEL_SIZE,
        )
        // Scale down as they scatter
        const scale = 1 - t * 0.8
        matrix.scale(new THREE.Vector3(scale, scale, scale))
        mesh.setMatrixAt(i, matrix)

        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }

      // Hide unused instances
      for (let i = eggVoxels.length; i < maxCount; i++) {
        matrix.setPosition(0, -1000, 0)
        matrix.scale(new THREE.Vector3(0, 0, 0))
        mesh.setMatrixAt(i, matrix)
      }

      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

      if (t >= 1) {
        progressRef.current = 0
        setCurrentPhase('reform')
      }
    } else if (currentPhase === 'reform') {
      progressRef.current += delta / REFORM_DURATION
      const t = Math.min(progressRef.current, 1)
      const ease = t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2 // ease in-out

      // Pet voxels converge from scattered positions to final positions
      for (let i = 0; i < petVoxels.length; i++) {
        const v = petVoxels[i]
        const scatter = scatterDirs[i % scatterDirs.length]

        const startX = scatter.x * 2
        const startY = scatter.y * 2
        const startZ = scatter.z * 2

        const finalX = v.x * VOXEL_SIZE
        const finalY = v.y * VOXEL_SIZE
        const finalZ = v.z * VOXEL_SIZE

        matrix.identity()
        matrix.setPosition(
          startX + (finalX - startX) * ease,
          startY + (finalY - startY) * ease,
          startZ + (finalZ - startZ) * ease,
        )
        mesh.setMatrixAt(i, matrix)

        color.setRGB(v.r / 255, v.g / 255, v.b / 255, THREE.SRGBColorSpace)
        mesh.setColorAt(i, color)
      }

      // Hide unused instances
      for (let i = petVoxels.length; i < maxCount; i++) {
        matrix.setPosition(0, -1000, 0)
        matrix.scale(new THREE.Vector3(0, 0, 0))
        mesh.setMatrixAt(i, matrix)
      }

      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

      if (t >= 1) {
        setCurrentPhase('complete')
        onComplete()
      }
    }
  })

  // Sync phase from props
  useMemo(() => {
    if (phase !== currentPhase && phase !== 'idle') {
      progressRef.current = 0
      setCurrentPhase(phase)
    }
  }, [phase])

  if (maxCount === 0) return null

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, maxCount]}>
      <boxGeometry args={[VOXEL_SIZE, VOXEL_SIZE, VOXEL_SIZE]} />
      <meshStandardMaterial roughness={0.4} metalness={0.1} />
    </instancedMesh>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/hatch/HatchTransition.tsx
git commit -m "feat: add HatchTransition component (voxel shatter → reform animation)"
```

---

### Task 17: Integration Verification

- [ ] **Step 1: Verify all imports resolve**

Run: `cd /Users/worthy/TestCode/pets && python -c "from backend.services.pipeline import PipelineRunner, PipelineResult; print('Pipeline OK')"`
Run: `cd /Users/worthy/TestCode/pets && python -c "from backend.services.world_map import WorldMapService; print('WorldMap OK')"`
Run: `cd /Users/worthy/TestCode/pets && python -c "from backend.services.mood_board import MoodBoardService; print('MoodBoard OK')"`

Expected: All three print OK

- [ ] **Step 2: Run all tests**

Run: `cd /Users/worthy/TestCode/pets && python -m pytest backend/tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Verify frontend builds**

Run: `cd /Users/worthy/TestCode/pets/frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit any fixes**

If any issues were found, fix them and commit:

```bash
git add -A
git commit -m "fix: resolve integration issues from pipeline implementation"
```
