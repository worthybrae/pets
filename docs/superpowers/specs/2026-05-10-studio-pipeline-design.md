# Studio Pipeline: Autonomous World-Building Pet AI

**Date**: 2026-05-10
**Status**: Approved

## Problem

The current AI loop is a single GPT-4o call per tick with a massive system prompt and 20+ tools. This produces:
- Incoherent builds — no persistent vision, each tick is stateless
- Low-quality output — the model spreads attention across personality, planning, spatial reasoning, and code generation simultaneously
- No feedback loop — the AI never evaluates or iterates on its own work
- No reactive evolution — conversations don't meaningfully shape the world over time
- Aesthetic disconnect — smooth shader eggs hatch into blocky 1x1 voxel pets

## Vision

A pet that autonomously builds and maintains its own voxel universe. The owner checks in daily to discover what the pet created. The world has narrative coherence and evolves reactively based on accumulated conversation themes. The world becomes a physical diary of the owner-pet relationship, filtered through the pet's personality.

## Design

### 1. Studio Pipeline (Sequential, All OpenAI)

Four stages run in sequence during each autonomous tick, passing structured documents forward. Each stage uses the model best suited to its task. All models are OpenAI.

#### Stage 1 — Dreamer (o4-mini, upgradeable to o4)

**Purpose**: Pure creative ideation. Decides *what* to build and *why*.

**Model note**: Start with o4-mini. If creative output quality is insufficient, upgrade to o4. This is a per-pet configurable knob — some pets may benefit from the stronger model.

**Reads**:
- Pet soul (personality document)
- Mood board (accumulated conversation themes)
- World journal (last ~5 build session entries)
- Critic's last review
- Current agenda
- World map (queryable spatial index of existing regions)

**Outputs**: A *creative brief* — prose describing what to build and why, with emotional intent. No coordinates, no voxel counts, no technical details.

**Example output**:
> "The eastern hillside feels empty. I want to build a terraced garden there — stone retaining walls with wildflowers spilling over the edges. My owner mentioned their grandmother's garden last week, and I keep thinking about it. The garden should feel overgrown and alive, not manicured."

#### Stage 2 — Architect (o4-mini)

**Purpose**: Spatial planning. Translates creative vision into a structured build plan.

**Reads**:
- Creative brief (from Dreamer)
- World map — spatial index of existing structures and regions
- Existing voxels near the target area (via scan)

**Outputs**: A *build plan* — structured JSON with project name, target region coordinates, phases, and operations per phase.

```json
{
  "project": "Terraced Garden",
  "region": {"x": [40, 70], "y": [0, 15], "z": [20, 50]},
  "region_description": "Three-tiered garden carved into the eastern hillside, overgrown with wildflowers",
  "region_tags": ["garden", "grandmother", "overgrown", "eastern-hill"],
  "phases": [
    {
      "name": "terrain",
      "description": "3 terraced levels carved into hillside, 5 blocks per tier",
      "operations": [
        {"type": "fill_region", "bounds": {...}, "color": {...}, "noise": 15}
      ]
    },
    {
      "name": "walls",
      "description": "rough stone retaining walls with variation",
      "operations": [...]
    },
    {
      "name": "flora",
      "description": "wildflowers, vines spilling over walls, tall grass",
      "operations": [...]
    }
  ],
  "relationships": {"south_of": "cottage", "overlooks": "lake"}
}
```

#### Stage 3 — Builder (GPT-4o)

**Purpose**: Code execution. Translates the build plan into actual voxel operations.

**Reads**: Build plan only. Does not need personality, mood board, or conversation history.

**Outputs**: Executed tool calls — `fill_region`, `place_sphere`, `place_cylinder`, `place_voxels`, `execute_code`. This is the only stage that modifies the world.

**Behavior**:
- Follows the plan's phases sequentially
- Can run one or multiple phases per tick depending on food budget
- Reports back what was actually placed (voxel counts, regions modified)
- May use `execute_code` for procedural generation (noise, fractals, organic shapes)

#### Stage 4 — Critic (o4-mini)

**Purpose**: Evaluate the build. Creates the feedback loop that makes quality improve over time.

**Reads**:
- Creative brief (original intent)
- Build plan (what was supposed to happen)
- Scan of what was actually built (voxel data from the affected region)
- World journal (broader context)

**Outputs**: A *review* — structured evaluation with what worked, what didn't, and what to do next session. Gets saved and becomes input for the Dreamer's next tick.

**Example output**:
> "The terracing reads well from a distance but the walls look too uniform — needs more noise/variation in the stone colors. The flowers are a nice touch but too sparse — increase density by 2-3x. Next session: add more flora density and break up the wall texture. The overall direction is strong — this is becoming a real place."

**Review structure**:
```json
{
  "overall_assessment": "strong direction, needs detail work",
  "strengths": ["terracing shape", "spatial placement relative to cottage"],
  "issues": [
    {"area": "walls", "problem": "too uniform", "suggestion": "add noise 20-30 to stone colors"},
    {"area": "flora", "problem": "too sparse", "suggestion": "increase density, add vine trails"}
  ],
  "next_session_priorities": ["flora density", "wall texture variation"],
  "region_status": "in_progress"
}
```

#### Pipeline Orchestration

The pipeline is orchestrated by a new `PipelineRunner` service:

1. Load shared context (soul, mood board, world map, journal, last review)
2. Run Dreamer → receive creative brief
3. Run Architect with creative brief → receive build plan
4. Run Builder with build plan → voxels placed in world
5. Scan the built region
6. Run Critic with brief + plan + scan → receive review
7. Persist: update world map regions, write journal entry, save review
8. Broadcast updates via WebSocket throughout step 4

Food is deducted for each API call (steps 2-6). Building operations (step 4) remain free.

### 2. World Map & Spatial Memory

Two new persistence layers that give the pet spatial awareness of its own world.

#### World Regions (`world_regions` table)

```sql
world_regions (
  id UUID PRIMARY KEY,
  pet_id UUID REFERENCES pets(id),
  name TEXT NOT NULL,
  description TEXT,
  tags TEXT[],
  status TEXT DEFAULT 'planned',  -- planned | in_progress | complete | needs_revision
  bounds_min_x INT, bounds_min_y INT, bounds_min_z INT,
  bounds_max_x INT, bounds_max_y INT, bounds_max_z INT,
  relationships JSONB DEFAULT '{}',  -- {"south_of": "cottage", "overlooks": "lake"}
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
)
```

**Queryable by**:
- Spatial proximity: "what's within 30 blocks of (x, y, z)?"
- Name/tag search: "where is the garden?"
- Status: "what's still in progress?"
- Relationships: "what's south of the cottage?"

#### World Journal (`world_journal` table)

```sql
world_journal (
  id UUID PRIMARY KEY,
  pet_id UUID REFERENCES pets(id),
  creative_brief TEXT,
  build_plan JSONB,
  critic_review JSONB,
  region_id UUID REFERENCES world_regions(id),
  voxels_placed INT,
  created_at TIMESTAMPTZ DEFAULT now()
)
```

The Dreamer reads the last ~5 journal entries. This provides narrative continuity — the pet knows what it recently built, what the Critic thought, and what it planned to do next.

#### How they interact

- **Architect** creates/updates `world_regions` entries when planning a new build
- **Critic** updates region status after review (`in_progress` → `complete` or `needs_revision`)
- **Dreamer** queries regions to understand its world spatially before ideating
- All stages can query nearby regions to avoid spatial conflicts

### 3. Mood Board & Reactive Evolution

Conversations between the owner and pet feed a persistent mood board that shapes the Dreamer's creative direction.

#### Theme Extraction

After each chat conversation, a lightweight extraction pass runs:
- Input: conversation messages
- Output: themes (topics, emotions, imagery) with relevance scores
- Model: GPT-4o-mini (cheap, fast)
- Example: *"I had a rough day, wish I could sit by the ocean"* → `{ocean: 0.8, calm: 0.7, escape: 0.6}`

#### Mood Board Table (`pet_mood_board`)

```sql
pet_mood_board (
  id UUID PRIMARY KEY,
  pet_id UUID REFERENCES pets(id),
  theme TEXT NOT NULL,
  weight FLOAT DEFAULT 1.0,
  moments TEXT[],  -- vivid specific references: "grandmother's wild roses"
  first_seen TIMESTAMPTZ DEFAULT now(),
  last_seen TIMESTAMPTZ DEFAULT now(),
  mention_count INT DEFAULT 1
)
```

**Weight mechanics**:
- Each mention increases weight by 1.0
- Weights decay by 0.1 per day (themes fade if not reinforced)
- Minimum weight: 0.1 (never fully forgotten)
- `moments` array stores specific vivid quotes/references worth remembering

**How the Dreamer uses it**:
- Mood board is injected into Dreamer's context as a ranked list of themes
- Heavy themes (weight > 5) shape the world's overall direction
- Moderate themes (2-5) influence individual projects
- Light themes (< 2) become ambient details and accents
- Moments provide specific imagery the pet can reference

**Evolution over time** (example):
- Week 1: Owner mentions ocean twice → weight 2 → a small pond with a dock appears
- Week 3: Ocean keeps coming up → weight 6 → pond has grown into a cove, lighthouse added
- Week 6: Owner talks about stargazing → space theme grows → lighthouse gets an observatory
- Week 10: Ocean mentions stop → weight decays → coastline stabilizes, no new ocean builds, but existing ocean structures remain

### 4. Voxel Aesthetic Overhaul

#### Voxel Eggs

Replace shader-based eggs with voxel-rendered eggs:
- Egg shape built from small cubes (0.25-0.5 unit voxels)
- Egg attributes express through voxel patterns:
  - **Shape**: Overall voxel silhouette (round, elongated, teardrop, etc.)
  - **Scales**: Surface texture patterns in voxel (checkerboard, stripes, spirals)
  - **Color**: Per-voxel coloring with the same color palette
  - **Size**: Voxel count scales with size attribute
  - **Mist**: Small floating voxel particles orbiting the egg
- Sets the aesthetic expectation from the first screen: this is a voxel world

#### Higher-Fidelity Pet Bodies

- Pet body voxels use 0.25 unit cubes (4x resolution per axis, 64x voxel count)
- Same `instancedMesh` rendering approach, just smaller scale
- Pets read as detailed "pixel art characters" — visually distinct from the 1x1 world voxels
- Creates natural visual hierarchy: pet is the highest-resolution thing on screen
- World voxels remain 1x1x1 — chunky and bold

#### Hatching Transition

Animated sequence bridging egg to pet:
1. Voxel egg displayed, user interacts to start hatching
2. Cracks appear — voxels break away from the shell in chunks
3. Egg shatters — all voxels scatter outward as particles
4. Particles swirl, change color, and reform into the pet's body shape
5. Pet takes its first steps
6. Backstory revealed

### 5. Changes to Existing Systems

#### `brain.py` Refactor

The current monolithic `PetBrain` class becomes a thin wrapper that delegates to the pipeline:
- **Chat interactions** (`user_chat` trigger): Still handled by a single model call (the pet responding in conversation). After the chat, theme extraction runs asynchronously.
- **Autonomous ticks** (`autonomous_tick` trigger): Routed to the new `PipelineRunner` instead of a single model call.
- **Birth** (`birth` trigger): First pipeline run. Dreamer gets special context: "This is your first moment. Build your birthplace."

#### Tools Refactor

Tools are reorganized by which pipeline stage uses them:
- **Builder-only tools**: `place_voxels`, `fill_region`, `place_sphere`, `place_cylinder`, `remove_voxels`, `execute_code`, `set_animation`
- **Architect tools**: `scan_world`, new `query_regions` tool
- **Dreamer tools**: `search_memories`, new `query_mood_board` tool, new `query_regions` tool
- **Shared tools**: `respond_to_user` (for chat, not pipeline)
- **Removed from pipeline**: `search_web`, `fetch_url` (these are chat-only)

#### Existing Memory System

The 3-tier memory system (raw events, digested notes, knowledge base) remains unchanged. The mood board is a new parallel system, not a replacement. Memories inform the pet's personality and conversation; the mood board informs its creative direction.

#### Food Economics

Each pipeline tick costs more than the current single-call approach:
- 4 API calls per tick (Dreamer + Architect + Builder + Critic)
- Theme extraction after chats (cheap, GPT-4o-mini)
- Building operations remain free
- Net cost per tick estimated at 3-4x current cost
- This is acceptable per the "quality first" decision — optimize later by tuning model selection per stage

### 6. New File Structure

```
backend/services/
  pipeline/
    runner.py          # PipelineRunner orchestrator
    dreamer.py         # Stage 1: creative ideation
    architect.py       # Stage 2: spatial planning
    builder.py         # Stage 3: voxel execution
    critic.py          # Stage 4: evaluation
    context.py         # Shared context loading (soul, mood board, world map)
  mood_board.py        # Theme extraction + mood board CRUD
  world_map.py         # World regions + journal CRUD + spatial queries
  brain.py             # Refactored: chat-only, delegates ticks to pipeline
  tools.py             # Refactored: tools organized by stage

backend/migrations/
  013_create_world_regions.sql
  014_create_world_journal.sql
  015_create_mood_board.sql

frontend/src/components/
  hatch/
    VoxelEgg.tsx       # New: voxel-based egg renderer
    EggScene.tsx       # Refactored: uses VoxelEgg instead of shaders
    HatchTransition.tsx # New: voxel shatter → reform animation
  world/
    PetEntity.tsx      # Modified: 0.25 unit voxels for pet body
```

## Out of Scope

- Social features (pet visits, messaging) — unchanged, not part of this redesign
- Food pricing changes — current economics remain
- Frontend world rendering changes (chunks, lighting, fog) — unchanged except pet voxel size
- Mobile/responsive design
- Multi-pet worlds
