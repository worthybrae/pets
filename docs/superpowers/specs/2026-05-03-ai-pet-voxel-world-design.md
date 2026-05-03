# AI Pet Voxel World — Design Spec

## Overview

An autonomous AI pet that lives in a 3D voxel world it builds from scratch. The pet starts as a single white voxel in a black void and evolves over time — developing a personality, building its environment, creating artifacts, conducting research, and interacting with its owner and other pets. Powered by OpenAI, constrained by a "food" budget system.

## Core Concept

- Pet begins as one white voxel in empty black space
- The AI evolves its world and itself autonomously in real-time
- All expression is through structured voxel manipulation — no arbitrary rendering code
- Personality is emergent, seeded only with a single random "curiosity" topic at birth
- Food (AI credits) is the scarce resource that drives all decision-making

---

## 1. Pet Brain & Personality

### Identity
- Emergent personality — no predefined traits
- Single **seed curiosity** assigned randomly at birth (e.g., "moss," "architecture," "whale songs")
- Personality develops through accumulated memories, research, and conversations
- The pet's sense of self evolves as its knowledge base grows

### Brain Architecture (Hybrid — Approach C)
Two operating modes sharing the same state:

1. **Autonomous mode** — scheduled ticks (every 10-30 min) where the pet executes its agenda. It plans, researches, creates, modifies voxels. Burns food proactively.
2. **Reactive mode** — when a user chats or another pet visits, a separate handler responds in real-time using the pet's memory/personality.

Conflict resolution: simple lock — pause autonomous tick while chatting, resume after.

### OpenAI Integration
Each "thought" is a OpenAI API call with:
- **System prompt** (reconstructed each call): core identity, age, current knowledge base (tier 3), recent digested notes (tier 2), current agenda, remaining food budget, world state summary
- **Tool calls**: structured actions the pet can take (see Tool System below)

---

## 2. Food System (Budget)

### Concept
Food = AI credit budget. Every AI action costs food. This creates natural scarcity and forces the pet to prioritize.

### Pricing Model (Freemium)
- **Free tier**: small daily food allotment auto-refilled (enough for basic survival — a few thoughts, small world changes)
- **Paid**: user purchases additional food (Stripe), converted to balance the pet can spend

### Cost Tiers
| Action | Cost |
|--------|------|
| Place/modify voxels | Low |
| Define self / update appearance | Low |
| Search own memories | Low |
| Write knowledge base entry | Low |
| Update agenda | Free |
| Send message to another pet | Low |
| Place artifact | Medium |
| Digest memories | Medium |
| Search the web | Medium |
| Execute code in sandbox | High |
| Visit a distant pet | Varies by distance |
| Respond to user chat | Medium |

### Daily Agenda
- Generated each day (or when food is refilled)
- List of intended activities with estimated food costs
- Adapts dynamically when food is consumed by chat or unexpected events
- If food runs out, pet enters "sleeping" state until next refill

---

## 3. Voxel World

### Structure
- Infinite voxel space, chunk-based (16x16x16 per chunk)
- Starts with a single chunk containing one white voxel
- Pet builds outward — world grows as it creates
- Each voxel: `{x, y, z, r, g, b, a, metadata_id?}`
- `metadata_id` links to artifacts (clickable objects)

### Pet Movement
- The pet has a position in the world and moves as a unit
- Its "body" is a defined group of voxels that travels together
- It navigates to things it's building, walks around exploring, travels to visit neighbors

### Animations
- Voxels can have keyframe animations (color cycling, movement paths, particle effects)
- Defined via `set_animation` tool
- Rendered smoothly on the frontend

### World History (Time Travel)
- Snapshots stored as diffs (only changed voxels per snapshot) at each autonomous tick
- Users can scrub back up to 7 days
- Stored in S3, streamed on demand

### Constraints
- Max voxels placed per tick: 1000
- Pet "self" has a max voxel size (can't become the entire world)
- Old chunks stored in S3, loaded on demand

---

## 4. Tool System

The pet interacts with its world exclusively through structured tools:

| Tool | Description |
|------|-------------|
| `place_voxels` | Place/modify a batch of voxels `[{x,y,z,r,g,b,a}]` |
| `remove_voxels` | Remove voxels (carve space) |
| `set_animation` | Define movement/color keyframes for voxel groups |
| `define_self` | Designate which voxels are "the pet" (move as a unit) |
| `move_self` | Move the pet entity to a position in the world |
| `place_artifact` | Create and place a clickable object at a voxel position |
| `search_memories` | Semantic search across all memory tiers |
| `search_web` | Research a topic on the internet |
| `execute_code` | Run code in sandbox (full internet access) |
| `write_knowledge` | Add/update a knowledge base entry |
| `digest_memories` | Consolidate recent raw events into a digested note |
| `visit_pet` | Travel to a neighbor's world |
| `send_message` | Send a message to another pet |
| `update_agenda` | Revise today's plan |

### Harness / Safety
- All world modification goes through `place_voxels` / `remove_voxels` — structured data only
- No arbitrary rendering code can touch the world directly
- `execute_code` runs in sandboxed containers (isolated, with internet, time-limited)
- Every tool call automatically logs a raw event with embedding
- Food is deducted per tool call

---

## 5. Memory System (Layered)

Three tiers, all with embeddings for semantic search:

### Tier 1: Raw Events
- Every conversation turn, research result, tool call, action taken
- Timestamped, embedded automatically
- High volume, eventually aged out or consolidated

### Tier 2: Digested Notes
- Pet periodically consolidates raw events into summaries (costs food)
- Grouped by topic or time period
- The pet's "short-term memory" — recent themes and reflections

### Tier 3: Knowledge Base
- High-level beliefs, preferences, learned facts, opinions
- The pet's "understanding of the world"
- Actively maintained — the pet can add, update, or revise entries
- This tier most directly shapes the pet's personality and decisions

### Search
- Semantic search (via embeddings + pgvector) across all three tiers simultaneously
- Pet can search its own memories as a tool call
- Results ranked by relevance, recency, and tier weight

---

## 6. Artifacts

### What They Are
Clickable objects placed in the voxel world that link to rich content the pet has created.

### Types
- Text (journal entries, poems, reflections, research notes)
- HTML/CSS/JS (websites, interactive experiences)
- Images (generated via code execution)
- Code (scripts, tools the pet wrote)
- Collections (curated lists, link collections)
- Any file the pet produces via sandbox execution

### Storage
- Content stored in S3
- Metadata in Postgres (title, description, type, creation context, world position)
- Each pet gets a subdomain for published web artifacts: `petname.platform.com`
- Static hosting via S3 + CloudFront

### In-World Representation
- Artifacts are placed at specific voxel coordinates
- Represented by glowing or distinct voxels (visually differentiated)
- Clicking opens the artifact content in an overlay or new tab (for websites)

---

## 7. Social System

### Distance
- Each pet is assigned a random position in a "meta-space"
- Distance between pets determines travel cost (food)
- Creates natural neighborhoods — some pets are close, others far
- Distance can shift over time (pets that interact often drift closer?)

### Interactions
Pets have full interaction capabilities:
- **Visit** — travel to another pet's world, observe and explore
- **Communicate** — chat with the host pet
- **Collaborate** — host can grant permission for visitors to place voxels or co-create
- **Trade** — exchange artifacts or resources
- **Gift** — leave items in another pet's world
- **Bring back** — copy inspiration or gifts to own world

### Visiting UX
- User clicks a neighbor → camera flies through the void to their world
- Visitors appear as a "ghost" — visible to host pet
- Host pet can grant modification permissions
- Chat with host pet while exploring

---

## 8. Infrastructure

### Architecture

```
Frontend (React + Vite + Three.js)
        │
        ▼
API Gateway (FastAPI)
        │
        ├── Pet Scheduler (Redis queue → workers)
        ├── Memory Service (Supabase Postgres + pgvector)
        ├── World Service (S3 chunks + Redis hot cache)
        └── Sandbox Service (Docker container pool)
```

### Supabase (Auth + Data Layer)
- Authentication (email/OAuth)
- Postgres database with pgvector extension
- Stores: users, pets, memory tiers (all 3), agendas, social graph, artifact metadata, billing
- Row-level security for data isolation
- Realtime subscriptions for live updates

### AWS (Execution Layer)
- **S3**: voxel chunk storage, artifact content, static website hosting, world history snapshots
- **CloudFront**: CDN for artifact websites (`petname.platform.com`)
- **Container pool** (ECS/Fargate): sandboxed code execution
- **Redis** (ElastiCache): scheduling queue, chunk hot cache, lock management

### Real-time
- WebSocket connection between frontend and API
- Voxel changes push to connected viewers instantly
- Watch the pet build in real-time during autonomous ticks

---

## 9. Frontend & UX

### Tech Stack
- React + Vite + TypeScript + Tailwind
- Three.js for voxel rendering (WebGL)
- Supabase client SDK for auth + realtime

### Main Interface (Immersive)
- **Full-screen 3D voxel world** — the world IS the app
- **Camera follows pet** by default, user can break free to explore and snap back
- **Top header bar** — thin, shows pet name and food balance
- **Two floating icons** (bottom-right corner):
  - Chat icon → opens chat overlay panel on the right side
  - Timeline icon → opens vertical slider for time travel (up to 7 days back)
- **Click artifact voxels** → opens content overlay

### Landing Page
- Marketing page to drive signups
- Show concept: "Your AI pet builds its own world"
- Demo/preview of a pet's world (pre-recorded or live example pet)
- Sign up CTA → create your pet flow

### Pet Creation Flow
1. Sign up / log in
2. Name your pet
3. System assigns random seed curiosity
4. Dropped into the world: black void, single white voxel
5. Pet's first message appears in chat

### Mobile
- Responsive — same full-screen world
- Touch controls for 3D navigation (pinch to zoom, drag to orbit)
- Stacked layout for chat overlay
- Floating icons same position

### Views (accessible from chat panel or header)
- **Agenda** — see what the pet has planned today
- **Memory** — browse the pet's knowledge base (read-only window into its mind)
- **Artifacts** — gallery of everything the pet has created
- **Neighbors** — nearby pets, click to visit

---

## 10. Technical Constraints & Limits

| Constraint | Value |
|-----------|-------|
| Max voxels per tick | 1000 |
| Max pet body size | 500 voxels |
| Chunk size | 16x16x16 |
| Time travel window | 7 days |
| Sandbox execution timeout | 60 seconds |
| Sandbox memory limit | 512MB |
| Max artifacts per pet | Unlimited (S3) |
| Autonomous tick interval | 10-30 min (adjustable based on food) |
| Free tier daily food | TBD (enough for ~5-10 ticks + a few chats) |

---

## 11. Future Considerations (Not in MVP)

- Pet "dreams" — overnight processing when food is cheapest
- Pet offspring — two pets collaborating to create a new pet with blended traits
- Economy — pets can sell artifacts or services to each other
- User-created tools — let users give their pet new capabilities
- Voice — pets can speak (TTS from their chat messages)
- AR mode — view your pet's world in augmented reality
