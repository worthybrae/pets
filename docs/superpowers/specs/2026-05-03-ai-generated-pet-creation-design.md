# AI-Generated Pet Creation

## Overview

Replace hardcoded pet shape templates with a single OpenAI structured output call that generates a unique voxel creature, personality (soul), starter world landmark, and backstory for every new pet. Stats are still rolled randomly server-side and fed into the LLM as creative constraints.

## Creation Flow

1. User enters name + curiosity (max 250 chars) on the Hatch page
2. Frontend starts egg animation (extended to 8s to cover LLM latency)
3. `POST /api/pets` hits the backend:
   a. Roll 7 stats using median-of-3 (unchanged)
   b. Determine rarity via weighted random (60/25/10/4/1%)
   c. Adjust stats to fit rarity tier
   d. Single OpenAI call with `{name, curiosity, stats, rarity}` → structured output returns `{pet_voxels, world_voxels, soul, backstory}`
   e. Runtime validation and clamping
   f. Store everything, return full pet to frontend
4. Frontend reveal phase renders the AI-generated pet voxels (not a template lookup)
5. World page renders pet voxels + world voxels as the initial chunk

If the LLM call fails, fall back to: single white cube pet, empty world, template backstory, minimal default soul. The pet still gets created.

## Stats

7 stats, each 1-10, rolled with median-of-3:

| Stat | Governs |
|------|---------|
| Curiosity | Drive to explore and learn |
| Creativity | Inventiveness in building and problem-solving |
| Social | Desire to interact with users and other pets |
| Focus | Ability to stay on task, depth of work |
| Energy | Activity level, how often they act |
| Resilience | How they handle setbacks, persistence |
| Humor | Playfulness, joke-telling, lightheartedness |

### Rarity Tiers (7 stats, total range 7-70)

| Rarity | Probability | Total Range |
|--------|------------|-------------|
| Common | 60% | 18-34 |
| Uncommon | 25% | 35-43 |
| Rare | 10% | 44-51 |
| Legendary | 4% | 52-60 |
| Mythic | 1% | 61-70 |

## Structured Output Schema

Uses OpenAI Structured Outputs (`response_format: { type: "json_schema" }`) for guaranteed schema conformance.

```json
{
  "name": "pet_creation",
  "strict": true,
  "schema": {
    "type": "object",
    "properties": {
      "pet_voxels": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "x": { "type": "integer" },
            "y": { "type": "integer" },
            "z": { "type": "integer" },
            "r": { "type": "integer" },
            "g": { "type": "integer" },
            "b": { "type": "integer" }
          },
          "required": ["x", "y", "z", "r", "g", "b"],
          "additionalProperties": false
        }
      },
      "world_voxels": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "x": { "type": "integer" },
            "y": { "type": "integer" },
            "z": { "type": "integer" },
            "r": { "type": "integer" },
            "g": { "type": "integer" },
            "b": { "type": "integer" }
          },
          "required": ["x", "y", "z", "r", "g", "b"],
          "additionalProperties": false
        }
      },
      "soul": { "type": "string" },
      "backstory": { "type": "string" }
    },
    "required": ["pet_voxels", "world_voxels", "soul", "backstory"],
    "additionalProperties": false
  }
}
```

## Runtime Validation

The schema guarantees structure. Runtime validation handles semantics:

- **Pet voxel count**: 150-400. Under 150: log warning, use as-is. Over 400: truncate to first 400.
- **World voxel count**: 200-500. Same treatment.
- **Color values**: Clamp each r/g/b to 0-255.
- **Pet coordinates**: Clamp to -10..10 per axis (pet centered at origin).
- **World coordinates**: Clamp to -16..16 per axis.
- **Soul length**: If empty or under 100 chars, substitute a template-generated fallback based on stats.
- **Backstory length**: If empty, substitute a template backstory.

## LLM Prompt Design

### System Prompt

```
You are a creature designer for a voxel world. You create unique 3D pixel-art creatures and environments using voxels (1x1x1 cubes on an integer grid).

Design principles:
- Build creatures layer-by-layer. y=0 is the ground, build upward.
- Use bilateral symmetry where appropriate (creatures look better symmetric).
- Use 3-5 main colors per creature, not random noise. Colors should feel cohesive.
- Creatures should be recognizable from multiple angles, not flat/2D.
- The creature should be centered around origin (0,0,0).
- World landmarks should sit on the y=0 ground plane and relate to the pet's curiosity.
```

### User Prompt

```
Create a pet and its world based on these attributes:

Name: {name}
Curiosity: {curiosity}
Rarity: {rarity}
Stats:
  Curiosity: {stats.curiosity}/10
  Creativity: {stats.creativity}/10
  Social: {stats.social}/10
  Focus: {stats.focus}/10
  Energy: {stats.energy}/10
  Resilience: {stats.resilience}/10
  Humor: {stats.humor}/10

Generate:

1. pet_voxels (150-400 voxels): A unique creature that embodies these stats. High energy = dynamic pose. High creativity = unusual features. High humor = playful expression. The rarity should influence complexity — mythic creatures are more elaborate than common ones.

2. world_voxels (200-500 voxels): A single landmark or feature that relates to the pet's curiosity "{curiosity}". This is the first thing in an otherwise empty void.

3. soul (~600 words): The pet's inner identity document with these sections:
   - Temperament: emotional baseline (e.g., cheerful, brooding, calm, chaotic)
   - Speech style: how they talk (e.g., formal, slang, poetic, terse, lots of questions)
   - Quirks: 2-3 specific behavioral habits
   - Fears: what makes them anxious or avoidant
   - Goals: what they want to achieve long-term
   - Worldview: how they interpret their existence
   - Initial questions: 3-5 things they're actively wondering about right now

   All sections should be shaped by the stats. A high-social low-focus pet is chatty and distractible. A high-resilience low-humor pet is stoic and serious. Make the personality feel coherent and alive.

4. backstory (2-3 sentences): Third-person origin story for the pet, referencing their name, curiosity, and strongest stat.
```

### Few-Shot Example

Include a small example (~30 voxels) of a simple creature in the system prompt to anchor the format and show what good voxel placement looks like.

## Pet Model Changes

### Fields Added
- `voxels`: `list[dict]` — pet's body voxels `[{x,y,z,r,g,b}, ...]`
- `soul`: `str` — full soul personality document
- `world_voxels`: `list[dict]` — starter world landmark voxels

### Fields Removed
- `species`: no longer needed (no templates)

### Fields Unchanged
- `id`, `owner_id`, `name`, `seed_curiosity`, `food_balance`, `status`, `position_x/y/z`, `created_at`, `rarity`, `stats`, `backstory`, `initial_curiosity`

## Code Changes

### Backend

**`backend/services/creation.py`**:
- Remove `SPECIES_BY_RARITY`, template backstories, `_generate_backstory()`
- Add `_generate_pet_with_llm(name, curiosity, stats, rarity)` — makes the OpenAI structured output call
- Add `_validate_creation_output(data)` — runtime validation/clamping
- Add fallback generation if LLM call fails
- Update `create_pet()` to call the new LLM function instead of picking species/template backstory
- Add humor to `_roll_stats()` and update `_adjust_stats_for_rarity()` ranges

**`backend/models/pet.py`**:
- Remove `species` field
- Add `voxels: list = []`, `soul: str = ""`, `world_voxels: list = []`

**`backend/services/brain.py`**:
- Update `_build_system_prompt()` to inject the soul text instead of generic identity lines

**`backend/api/pets.py`**:
- No route changes needed, just passes through the new fields

### Frontend

**`frontend/src/data/petShapes.ts`**: Delete the shape templates. Move `rarityColors` and `Rarity` type to a new `frontend/src/data/rarity.ts` since the Hatch reveal UI still uses them for badge styling.

**`frontend/src/pages/World.tsx`**:
- Read `pet.voxels` directly instead of calling `getPetVoxels(pet.species)`
- Pass `pet.world_voxels` as the initial chunk to `WorldScene`

**`frontend/src/pages/Hatch.tsx`**:
- `PetReveal` reads voxels from `petData.voxels` instead of `petShapes[species]`
- Remove species display (pet is unique, no species label)
- Extend egg animation from 3.5s to 8s
- Handle case where API response arrives after animation: show loading shimmer until data ready

**`frontend/src/components/world/PetEntity.tsx`**:
- No changes needed — already renders whatever voxels it receives

## Brain Integration

The soul replaces the generic identity in the brain's system prompt:

```
You are {name}. Here is your soul — this is who you are:

{soul}

Your stats: curiosity={X}, creativity={X}, social={X}, focus={X}, energy={X}, resilience={X}, humor={X}
```

The brain reads the soul on every `think()` call (chat and autonomous ticks). Personality is consistent across all interactions.

### Future: Self-Modification

The data model supports a `modify_self(voxels)` tool that updates the pet's voxel body. A pet could grow, change color, or evolve over time. Not in scope for this implementation but the architecture enables it.

## Latency & Cost

- **Egg animation**: Extended to 8s (from 3.5s) to cover LLM generation
- **Expected LLM time**: 3-6s for GPT-4o structured output with ~5000 output tokens
- **Cost per hatch**: ~$0.02-0.04 (input ~1000 tokens + output ~5000 tokens at GPT-4o rates)
- **Fallback**: If LLM takes >10s or fails, use white cube + empty world + template soul

## Error Handling

| Failure | Fallback |
|---------|----------|
| OpenAI API error | White cube pet, empty world, template soul/backstory |
| Invalid voxel data | Clamp coordinates/colors, use what's valid |
| Too few pet voxels | Use as-is (even 10 voxels is a valid pet) |
| Too many voxels | Truncate to limit |
| Empty soul | Generate template from stats |
| Timeout (>10s) | Use fallback, log for monitoring |
