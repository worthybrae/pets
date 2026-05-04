# Egg Rarity System Design

## Overview

Replace the current blob/shape system on the Hatch page with an egg rarity system. Each visit generates a random egg with emergent rarity determined by its attribute combination. The egg is the visual centerpiece of the hatching flow — it grows, pulses, reveals stats, and ultimately cracks open to reveal the voxel pet.

## Egg Attributes

5 attributes, each with multiple options across 5 rarity tiers:

| Attribute | Visual Role | Shader Implementation |
|-----------|-------------|----------------------|
| **Shape** | Egg silhouette | Vertex displacement (round, elongated, squat, teardrop, bulbous) |
| **Scales** | Surface pattern | Fragment shader noise/pattern (none/smooth, hexagonal, diamond, spiral, cracked) |
| **Color** | Base hue + specular | Uniforms (earth tones, jewel tones, iridescent, obsidian, etc.) |
| **Size** | Scale multiplier | Uniform scale (tiny, small, standard, large, massive) |
| **Mist** | Rim glow / atmosphere | Fragment rim lighting + opacity (none, faint, wispy, radiant, ethereal) |

### Probability Per Tier (per attribute roll)

- Common: 40%
- Uncommon: 25%
- Rare: 20%
- Legendary: 14%
- Mythic: 1%

### Point System

Each attribute's rarity tier awards points:

- Common = 0
- Uncommon = 0.5
- Rare = 1
- Legendary = 1.5
- Mythic = 2

Total possible range: 0–10 (sum of 5 attributes).

### Overall Egg Rarity Bands

- 0–2: Common
- 2.1–4: Uncommon
- 4.1–6: Rare
- 6.1–8: Legendary
- 8.1–10: Mythic

## Naming

Compound name formula: `[Size modifier?] [Color] [Scales] [Shape]`

- Size only appears if non-standard (Tiny/Large/Massive prefix; Standard omitted)
- Mist does not appear in name — it's a visual effect shown in the tooltip
- Examples:
  - "Obsidian Hexscale Teardrop"
  - "Massive Iridescent Smooth Orb"
  - "Tiny Amber Cracked Bulb"

## Display

### Always Visible (above egg)

- Egg name
- Overall rarity badge (color-coded per existing `rarityColors`)
- Point score (e.g., "6.5 / 10")

### Tooltip Card (on hover)

- Lists all 5 attributes with their individual rarity tier (color-coded)
- Shows which stats each attribute biases
- Shows mist level if present

## Stat System

### Attribute → Stat Bias

Each attribute influences specific stats:

- **Shape** → resilience, energy
- **Scales** → focus, creativity
- **Color** → social, humor
- **Size** → energy, resilience
- **Mist** → curiosity, creativity

The rarity tier of each attribute determines the strength of its bias (higher tier = wider/higher stat range for those stats).

### Stat Ranges

Each egg's attribute combination produces a specific min/max range for each of the 7 stats (curiosity, creativity, social, focus, energy, resilience, humor). Stats are rolled within those ranges.

### Quality Badge (Three Tiers)

After stats roll, compare actual values to the egg's possible range:

- **Enhanced** (top 25% of range) — gold accent
- **Neutral** (middle 50%) — no badge
- **Fractured** (bottom 25%) — cracked/dim accent

## Hatch Flow

### Phase 1 — Idle (egg appears)

- Egg renders at base size, slow gentle rotation
- Heart beats at resting pace (~1 beat/sec)
- Scale pattern subtly catches light as it rotates
- Mist (if present) drifts slowly around rim
- Name + rarity visible above, hover for tooltip

### Phase 2 — Hatching (user clicks Hatch)

- Egg grows ~2x over 2 seconds
- Heart beat accelerates (2–3 beats/sec), glow intensifies
- Scale pattern becomes more pronounced (deeper displacement)
- Camera pulls in slightly

### Phase 3 — Stats Reveal

- Stats card appears (bars animate in one by one)
- Egg continues pulsing at elevated rate
- Quality badge (Enhanced/Fractured) appears after all stats shown
- Sign-in button appears below

### Phase 4 — Generating (after sign-in, LLM running)

- Egg grows further, beats even faster
- Scales begin to glow/crack with light seeping through
- Mist intensifies regardless of attribute (building energy)
- Status text below ("Shaping consciousness...", etc.)

### Phase 5 — Hatch / Reveal

- Flash of light
- Egg shell fragments dissolve (shader dissolve via noise threshold on fragment alpha)
- Voxel creature assembles from the center (existing PetReveal system)
- Camera pulls back to show creature
- Full profile card slides in (name, stats, backstory typewriter, "Begin Journey" button)

## Shader Architecture

**Single custom shader** handles the entire egg:

- **Vertex shader**: Organic egg silhouette via displacement (shape attribute controls parameters), scale bump pattern
- **Fragment shader**: Color with subsurface scattering approximation, scale pattern overlay, inner heart glow (emissive pulse), rim mist effect, dissolve for hatching
- **Uniforms**: time, morph/growth, beat intensity, dissolve progress, attribute parameters (shape params, scale type, color RGB, mist intensity)

All phase transitions are uniform tweens — no geometry swaps.

## File Structure

### New Files

- `frontend/src/components/hatch/EggScene.tsx` — 3D egg scene (replaces BlobScene)
- `frontend/src/components/hatch/eggAttributes.ts` — attribute pools, probabilities, stat biases, naming
- `frontend/src/components/hatch/eggShaders.ts` — GLSL vertex + fragment shaders
- `frontend/src/components/hatch/EggTooltip.tsx` — hover tooltip card
- `frontend/src/components/hatch/PetReveal.tsx` — extracted from BlobScene (reused as-is)

### Modified Files

- `frontend/src/components/hatch/gameLogic.ts` — new egg rolling logic (roll attributes → compute points → determine rarity → compute stat ranges → roll stats)
- `frontend/src/components/hatch/types.ts` — add EggProfile type, update Phase type
- `frontend/src/pages/Hatch.tsx` — new flow using EggScene, tooltip, egg-based stats

### Removed Files

- `frontend/src/components/hatch/BlobScene.tsx` — replaced by EggScene
- `frontend/src/components/hatch/shaders.ts` — replaced by eggShaders
- `frontend/src/components/hatch/presets.ts` — replaced by eggAttributes

### Unchanged

- `frontend/src/data/rarity.ts` — reused as-is
- `frontend/src/components/hatch/StatsCard.tsx` — reused, add Enhanced/Fractured badge
- Backend API — no changes needed (still receives stats + rarity)

## Rendering Details

- **Beating heart**: All eggs share the same core glow that pulses. Implemented as a radial emissive term in the fragment shader, modulated by a sine-based beat function. Intensity increases with phase progression.
- **Organic shape**: Vertex displacement using a combination of spherical harmonics and noise, parameterized by shape attribute (aspect ratio, pointedness, roundness).
- **Scale pattern**: Fragment-space pattern using Voronoi or hex tiling, with edge highlighting. Pattern type selected by scales attribute. Depth increases during hatching phase.
- **Mist**: Fresnel-based rim glow with animated noise for drift. Intensity from 0 (none) to full ethereal based on attribute.
- **Dissolve**: Noise-threshold alpha discard in fragment shader, revealing nothing (or white flash) as egg shell vanishes.
