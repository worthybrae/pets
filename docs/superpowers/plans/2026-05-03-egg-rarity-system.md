# Egg Rarity System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the blob/shape system on the Hatch page with an egg rarity system where each visit generates a random egg with emergent rarity, stat biases, and a full hatching flow.

**Architecture:** Single custom GLSL shader renders an organic egg with surface scale patterns, beating heart core, and mist effects. Egg attributes (shape, scales, color, size, mist) are rolled independently with tier-based probabilities. Points from each attribute's tier sum to determine overall rarity. Each attribute biases specific stats, and a quality badge (Enhanced/Neutral/Fractured) reflects how well the stats rolled within the egg's ranges.

**Tech Stack:** React 19, TypeScript, Three.js r184, @react-three/fiber v9, @react-three/drei, Tailwind CSS v4, Vite

**Note:** This project has no test runner configured (no vitest/jest). Steps use `tsc --noEmit` for type checking and `vite build` for build verification. Visual verification is done in the browser via `npm run dev`.

---

## File Structure

### New Files
- `frontend/src/components/hatch/eggAttributes.ts` — attribute pools, probabilities, point values, stat biases, naming logic
- `frontend/src/components/hatch/eggShaders.ts` — GLSL vertex + fragment shaders for the organic egg
- `frontend/src/components/hatch/EggScene.tsx` — R3F scene component (egg mesh, glow halo, ground shadow, camera, pet reveal)
- `frontend/src/components/hatch/EggTooltip.tsx` — hover tooltip showing attribute breakdown
- `frontend/src/components/hatch/PetReveal.tsx` — extracted from BlobScene.tsx (voxel creature assembly animation)

### Modified Files
- `frontend/src/components/hatch/gameLogic.ts` — replace old roll/rarity functions with egg-based system
- `frontend/src/components/hatch/types.ts` — add EggProfile, EggAttribute types; keep Phase, PetData, HatchProps
- `frontend/src/components/hatch/StatsCard.tsx` — add QualityBadge component (Enhanced/Fractured)
- `frontend/src/pages/Hatch.tsx` — rewrite flow to use EggScene, egg-based stats, tooltip, quality badge

### Removed Files (after all tasks complete)
- `frontend/src/components/hatch/BlobScene.tsx`
- `frontend/src/components/hatch/shaders.ts`
- `frontend/src/components/hatch/presets.ts`

---

## Task 1: Types & Attribute Data

**Files:**
- Modify: `frontend/src/components/hatch/types.ts`
- Create: `frontend/src/components/hatch/eggAttributes.ts`

- [ ] **Step 1: Update types.ts with egg types**

Replace the entire file:

```typescript
import type { Rarity } from '../../data/rarity'

export type Phase = 'idle' | 'hatching' | 'stats' | 'generating' | 'reveal'

export type AttributeTier = 'common' | 'uncommon' | 'rare' | 'legendary' | 'mythic'

export interface AttributeOption {
  name: string
  tier: AttributeTier
  /** Shader uniform value or identifier */
  value: number
}

export interface RolledAttribute {
  category: string
  option: AttributeOption
  points: number
}

export interface EggProfile {
  attributes: RolledAttribute[]
  name: string
  totalPoints: number
  rarity: Rarity
  /** Per-stat [min, max] ranges derived from attribute biases */
  statRanges: Record<string, [number, number]>
}

export interface PetData {
  id: string
  name: string
  rarity: Rarity
  stats: Record<string, number>
  backstory: string
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
}

export interface HatchProps {
  onHatch: (stats: Record<string, number>, rarity: string) => Promise<any>
  onComplete: (petData: any) => void
  session: any
}

export type QualityTier = 'enhanced' | 'neutral' | 'fractured'
```

- [ ] **Step 2: Create eggAttributes.ts**

```typescript
import type { Rarity } from '../../data/rarity'
import type { AttributeOption, AttributeTier, RolledAttribute, EggProfile, QualityTier } from './types'

// ── Tier config ──

const TIER_PROBABILITIES: Record<AttributeTier, number> = {
  common: 40,
  uncommon: 25,
  rare: 20,
  legendary: 14,
  mythic: 1,
}

const TIER_POINTS: Record<AttributeTier, number> = {
  common: 0,
  uncommon: 0.5,
  rare: 1,
  legendary: 1.5,
  mythic: 2,
}

// ── Attribute pools ──

const SHAPE_OPTIONS: AttributeOption[] = [
  { name: 'Round',     tier: 'common',    value: 0 },
  { name: 'Oval',      tier: 'common',    value: 1 },
  { name: 'Squat',     tier: 'uncommon',  value: 2 },
  { name: 'Elongated', tier: 'uncommon',  value: 3 },
  { name: 'Teardrop',  tier: 'rare',      value: 4 },
  { name: 'Bulbous',   tier: 'rare',      value: 5 },
  { name: 'Gourd',     tier: 'legendary', value: 6 },
  { name: 'Spire',     tier: 'mythic',    value: 7 },
]

const SCALES_OPTIONS: AttributeOption[] = [
  { name: 'Smooth',    tier: 'common',    value: 0 },
  { name: 'Stippled',  tier: 'common',    value: 1 },
  { name: 'Hexscale',  tier: 'uncommon',  value: 2 },
  { name: 'Diamond',   tier: 'uncommon',  value: 3 },
  { name: 'Spiral',    tier: 'rare',      value: 4 },
  { name: 'Cracked',   tier: 'rare',      value: 5 },
  { name: 'Runic',     tier: 'legendary', value: 6 },
  { name: 'Prismatic', tier: 'mythic',    value: 7 },
]

const COLOR_OPTIONS: AttributeOption[] = [
  { name: 'Stone',     tier: 'common',    value: 0 },
  { name: 'Moss',      tier: 'common',    value: 1 },
  { name: 'Amber',     tier: 'uncommon',  value: 2 },
  { name: 'Cobalt',    tier: 'uncommon',  value: 3 },
  { name: 'Crimson',   tier: 'rare',      value: 4 },
  { name: 'Violet',    tier: 'rare',      value: 5 },
  { name: 'Obsidian',  tier: 'legendary', value: 6 },
  { name: 'Iridescent', tier: 'mythic',   value: 7 },
]

const SIZE_OPTIONS: AttributeOption[] = [
  { name: 'Tiny',      tier: 'common',    value: 0 },
  { name: 'Small',     tier: 'common',    value: 1 },
  { name: 'Standard',  tier: 'uncommon',  value: 2 },
  { name: 'Large',     tier: 'rare',      value: 3 },
  { name: 'Massive',   tier: 'legendary', value: 4 },
  { name: 'Colossal',  tier: 'mythic',    value: 5 },
]

const MIST_OPTIONS: AttributeOption[] = [
  { name: 'None',      tier: 'common',    value: 0 },
  { name: 'Faint',     tier: 'uncommon',  value: 1 },
  { name: 'Wispy',     tier: 'rare',      value: 2 },
  { name: 'Radiant',   tier: 'legendary', value: 3 },
  { name: 'Ethereal',  tier: 'mythic',    value: 4 },
]

const ATTRIBUTE_POOLS: { category: string; options: AttributeOption[] }[] = [
  { category: 'shape',  options: SHAPE_OPTIONS },
  { category: 'scales', options: SCALES_OPTIONS },
  { category: 'color',  options: COLOR_OPTIONS },
  { category: 'size',   options: SIZE_OPTIONS },
  { category: 'mist',   options: MIST_OPTIONS },
]

// ── Stat biases ──
// Each attribute category influences specific stats.
// The tier multiplier scales the bias strength.

const STAT_NAMES = ['curiosity', 'creativity', 'social', 'focus', 'energy', 'resilience', 'humor'] as const

const STAT_BIASES: Record<string, string[]> = {
  shape:  ['resilience', 'energy'],
  scales: ['focus', 'creativity'],
  color:  ['social', 'humor'],
  size:   ['energy', 'resilience'],
  mist:   ['curiosity', 'creativity'],
}

// ── Rolling logic ──

function rollTier(): AttributeTier {
  const roll = Math.random() * 100
  let cumulative = 0
  for (const [tier, prob] of Object.entries(TIER_PROBABILITIES) as [AttributeTier, number][]) {
    cumulative += prob
    if (roll < cumulative) return tier
  }
  return 'common'
}

function pickOption(options: AttributeOption[], tier: AttributeTier): AttributeOption {
  const matching = options.filter(o => o.tier === tier)
  return matching[Math.floor(Math.random() * matching.length)]
}

function computeRarity(totalPoints: number): Rarity {
  if (totalPoints > 8) return 'mythic'
  if (totalPoints > 6) return 'legendary'
  if (totalPoints > 4) return 'rare'
  if (totalPoints > 2) return 'uncommon'
  return 'common'
}

function computeStatRanges(attributes: RolledAttribute[]): Record<string, [number, number]> {
  const ranges: Record<string, [number, number]> = {}

  // Base range for all stats
  for (const stat of STAT_NAMES) {
    ranges[stat] = [1, 6]
  }

  // Each attribute's tier widens the range for its biased stats
  for (const attr of attributes) {
    const biasedStats = STAT_BIASES[attr.category] || []
    const tierBonus = TIER_POINTS[attr.option.tier]
    for (const stat of biasedStats) {
      const [min, max] = ranges[stat]
      // Increase both min and max based on tier, capped at 10
      ranges[stat] = [
        Math.min(10, min + Math.floor(tierBonus)),
        Math.min(10, max + Math.ceil(tierBonus * 2)),
      ]
    }
  }

  return ranges
}

// ── Naming ──

function buildEggName(attributes: RolledAttribute[]): string {
  const parts: string[] = []
  const sizeAttr = attributes.find(a => a.category === 'size')
  if (sizeAttr && sizeAttr.option.name !== 'Standard') {
    parts.push(sizeAttr.option.name)
  }
  const colorAttr = attributes.find(a => a.category === 'color')
  if (colorAttr) parts.push(colorAttr.option.name)
  const scalesAttr = attributes.find(a => a.category === 'scales')
  if (scalesAttr) parts.push(scalesAttr.option.name)
  const shapeAttr = attributes.find(a => a.category === 'shape')
  if (shapeAttr) parts.push(shapeAttr.option.name)
  return parts.join(' ')
}

// ── Public API ──

export function rollEgg(): EggProfile {
  const attributes: RolledAttribute[] = ATTRIBUTE_POOLS.map(pool => {
    const tier = rollTier()
    const option = pickOption(pool.options, tier)
    return {
      category: pool.category,
      option,
      points: TIER_POINTS[tier],
    }
  })

  const totalPoints = attributes.reduce((sum, a) => sum + a.points, 0)
  const rarity = computeRarity(totalPoints)
  const name = buildEggName(attributes)
  const statRanges = computeStatRanges(attributes)

  return { attributes, name, totalPoints, rarity, statRanges }
}

export function rollStatsFromEgg(egg: EggProfile): Record<string, number> {
  const stats: Record<string, number> = {}
  for (const stat of STAT_NAMES) {
    const [min, max] = egg.statRanges[stat]
    stats[stat] = min + Math.floor(Math.random() * (max - min + 1))
  }
  return stats
}

export function computeQuality(stats: Record<string, number>, egg: EggProfile): QualityTier {
  let totalActual = 0
  let totalMin = 0
  let totalMax = 0

  for (const stat of STAT_NAMES) {
    totalActual += stats[stat]
    const [min, max] = egg.statRanges[stat]
    totalMin += min
    totalMax += max
  }

  const range = totalMax - totalMin
  if (range === 0) return 'neutral'

  const position = (totalActual - totalMin) / range
  if (position >= 0.75) return 'enhanced'
  if (position <= 0.25) return 'fractured'
  return 'neutral'
}

export { STAT_NAMES, TIER_POINTS }
```

- [ ] **Step 3: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/hatch/types.ts frontend/src/components/hatch/eggAttributes.ts
git commit -m "feat: add egg attribute system with rolling, naming, and stat biases"
```

---

## Task 2: Egg Shaders

**Files:**
- Create: `frontend/src/components/hatch/eggShaders.ts`

- [ ] **Step 1: Create eggShaders.ts**

This shader renders an organic egg shape via vertex displacement, with scale patterns, beating heart glow, mist rim effect, and dissolve for hatching.

```typescript
// Simplex Noise (Ashima Arts)
const NOISE_GLSL = /* glsl */ `
vec3 mod289(vec3 x){return x-floor(x*(1./289.))*289.;}
vec4 mod289(vec4 x){return x-floor(x*(1./289.))*289.;}
vec4 permute(vec4 x){return mod289(((x*34.)+1.)*x);}
vec4 taylorInvSqrt(vec4 r){return 1.79284291400159-.85373472095314*r;}

float snoise(vec3 v){
  const vec2 C=vec2(1./6.,1./3.);
  const vec4 D=vec4(0.,.5,1.,2.);
  vec3 i=floor(v+dot(v,C.yyy));
  vec3 x0=v-i+dot(i,C.xxx);
  vec3 g=step(x0.yzx,x0.xyz);
  vec3 l=1.-g;
  vec3 i1=min(g.xyz,l.zxy);
  vec3 i2=max(g.xyz,l.zxy);
  vec3 x1=x0-i1+C.xxx;
  vec3 x2=x0-i2+C.yyy;
  vec3 x3=x0-D.yyy;
  i=mod289(i);
  vec4 p=permute(permute(permute(
    i.z+vec4(0.,i1.z,i2.z,1.))
    +i.y+vec4(0.,i1.y,i2.y,1.))
    +i.x+vec4(0.,i1.x,i2.x,1.));
  float n_=.142857142857;
  vec3 ns=n_*D.wyz-D.xzx;
  vec4 j=p-49.*floor(p*ns.z*ns.z);
  vec4 x_=floor(j*ns.z);
  vec4 y_=floor(j-7.*x_);
  vec4 x=x_*ns.x+ns.yyyy;
  vec4 y=y_*ns.x+ns.yyyy;
  vec4 h=1.-abs(x)-abs(y);
  vec4 b0=vec4(x.xy,y.xy);
  vec4 b1=vec4(x.zw,y.zw);
  vec4 s0=floor(b0)*2.+1.;
  vec4 s1=floor(b1)*2.+1.;
  vec4 sh=-step(h,vec4(0.));
  vec4 a0=b0.xzyw+s0.xzyw*sh.xxyy;
  vec4 a1=b1.xzyw+s1.xzyw*sh.zzww;
  vec3 p0=vec3(a0.xy,h.x);
  vec3 p1=vec3(a0.zw,h.y);
  vec3 p2=vec3(a1.xy,h.z);
  vec3 p3=vec3(a1.zw,h.w);
  vec4 norm=taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0*=norm.x;p1*=norm.y;p2*=norm.z;p3*=norm.w;
  vec4 m=max(.6-vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)),0.);
  m=m*m;
  return 42.*dot(m*m,vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}
`

export const EGG_VERT = /* glsl */ `
uniform float uTime;
uniform float uGrowth;    // 0 = idle size, 1 = hatching, 2+ = generating
uniform float uDissolve;  // 0..1 for hatch reveal
uniform float uBeat;      // 0..1 heartbeat pulse
uniform float uSeed;
uniform float uShapeType; // 0=round, 1=oval, 2=squat, 3=elongated, 4=teardrop, 5=bulbous, 6=gourd, 7=spire
uniform float uScaleType; // 0=smooth, 1=stippled, 2=hex, 3=diamond, 4=spiral, 5=cracked, 6=runic, 7=prismatic
uniform float uSizeScale; // overall size multiplier

varying vec3 vNormal;
varying vec3 vWorldPos;
varying vec3 vLocalPos;

${NOISE_GLSL}

// Egg shape displacement — modifies a sphere into an organic egg
vec3 eggDisplace(vec3 pos, vec3 nrm) {
  // Base egg: taller than wide, narrower at top
  float y = pos.y;

  // Shape parameters based on uShapeType
  float topNarrow = 0.7;   // how much the top narrows
  float widthScale = 1.0;  // overall width
  float heightScale = 1.3; // overall height
  float asymmetry = 0.15;  // top-bottom asymmetry

  // Round (0)
  if (uShapeType < 0.5) {
    topNarrow = 0.6; widthScale = 1.0; heightScale = 1.1; asymmetry = 0.1;
  }
  // Oval (1)
  else if (uShapeType < 1.5) {
    topNarrow = 0.65; widthScale = 0.85; heightScale = 1.35; asymmetry = 0.12;
  }
  // Squat (2)
  else if (uShapeType < 2.5) {
    topNarrow = 0.55; widthScale = 1.15; heightScale = 0.9; asymmetry = 0.18;
  }
  // Elongated (3)
  else if (uShapeType < 3.5) {
    topNarrow = 0.7; widthScale = 0.75; heightScale = 1.6; asymmetry = 0.1;
  }
  // Teardrop (4)
  else if (uShapeType < 4.5) {
    topNarrow = 0.8; widthScale = 0.9; heightScale = 1.4; asymmetry = 0.25;
  }
  // Bulbous (5)
  else if (uShapeType < 5.5) {
    topNarrow = 0.5; widthScale = 1.1; heightScale = 1.2; asymmetry = 0.2;
  }
  // Gourd (6)
  else if (uShapeType < 6.5) {
    topNarrow = 0.75; widthScale = 1.0; heightScale = 1.5; asymmetry = 0.3;
  }
  // Spire (7)
  else {
    topNarrow = 0.85; widthScale = 0.7; heightScale = 1.8; asymmetry = 0.15;
  }

  // Apply egg shape: narrow the top, widen the bottom
  float normalizedY = y / heightScale;
  float topFactor = 1.0 - max(0.0, normalizedY) * topNarrow;
  float bottomBulge = 1.0 + max(0.0, -normalizedY) * asymmetry;
  float radialScale = widthScale * topFactor * bottomBulge;

  vec3 displaced = vec3(pos.x * radialScale, pos.y * heightScale, pos.z * radialScale);

  // Subtle organic noise displacement
  float n1 = snoise(displaced * 1.8 + uTime * 0.03 + vec3(uSeed)) * 0.015;
  float n2 = snoise(displaced * 3.5 + uTime * 0.05 + vec3(uSeed * 7.13)) * 0.008;

  // Heartbeat pulse
  float heartbeat = uBeat * 0.03;

  // Breathing
  float breath = sin(uTime * 0.4) * 0.008;

  float totalDisp = n1 + n2 + heartbeat + breath;

  // Scale pattern bump (subtle vertex displacement for texture)
  float scaleBump = 0.0;
  if (uScaleType > 0.5) {
    float scaleNoise = snoise(displaced * (4.0 + uScaleType * 0.5) + vec3(uSeed * 3.0));
    scaleBump = scaleNoise * 0.008 * min(uScaleType / 3.0, 1.0);
  }

  displaced += nrm * (totalDisp + scaleBump);

  // Apply growth and size
  float scale = uSizeScale * (0.8 + uGrowth * 0.6);
  displaced *= scale;

  // Dissolve shrink
  displaced *= 1.0 - uDissolve * 0.3;

  return displaced;
}

void main() {
  vec3 nrm = normalize(normal);
  vec3 pos = eggDisplace(position, nrm);

  vNormal = normalize(normalMatrix * nrm);
  vWorldPos = (modelMatrix * vec4(pos, 1.0)).xyz;
  vLocalPos = position;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
`

export const EGG_FRAG = /* glsl */ `
varying vec3 vNormal;
varying vec3 vWorldPos;
varying vec3 vLocalPos;

uniform float uTime;
uniform float uGrowth;
uniform float uDissolve;
uniform float uBeat;
uniform float uSeed;
uniform float uScaleType;
uniform float uMistIntensity; // 0=none, 1=faint, 2=wispy, 3=radiant, 4=ethereal
uniform vec3 uBaseColor;
uniform vec3 uCoreColor;      // heart glow color
uniform vec3 uSpecColor;      // specular highlight tint

${NOISE_GLSL}

// Scale pattern in fragment space
float scalePattern(vec3 p, float scaleType) {
  if (scaleType < 0.5) return 0.0; // Smooth — no pattern

  float pattern = 0.0;

  // Stippled (1)
  if (scaleType < 1.5) {
    pattern = snoise(p * 12.0 + vec3(uSeed)) * 0.5 + 0.5;
    pattern = smoothstep(0.4, 0.6, pattern) * 0.15;
  }
  // Hexscale (2)
  else if (scaleType < 2.5) {
    float hex = snoise(p * 8.0 + vec3(uSeed));
    float edges = abs(hex);
    pattern = smoothstep(0.02, 0.08, edges) * 0.2;
    pattern = 1.0 - pattern; // invert for cell edges
    pattern *= 0.15;
  }
  // Diamond (3)
  else if (scaleType < 3.5) {
    vec3 sp = p * 6.0;
    float d = abs(fract(sp.x + sp.y) - 0.5) + abs(fract(sp.y + sp.z) - 0.5);
    pattern = smoothstep(0.3, 0.35, d) * 0.18;
  }
  // Spiral (4)
  else if (scaleType < 4.5) {
    float angle = atan(p.z, p.x);
    float r = length(p.xz);
    float spiral = sin(angle * 3.0 + p.y * 8.0 + uTime * 0.1) * 0.5 + 0.5;
    pattern = spiral * 0.12;
  }
  // Cracked (5)
  else if (scaleType < 5.5) {
    float crack1 = abs(snoise(p * 5.0 + vec3(uSeed)));
    float crack2 = abs(snoise(p * 10.0 + vec3(uSeed * 2.0)));
    pattern = smoothstep(0.0, 0.05, crack1) * 0.1;
    pattern += smoothstep(0.0, 0.03, crack2) * 0.08;
  }
  // Runic (6)
  else if (scaleType < 6.5) {
    float rune1 = snoise(p * 4.0 + vec3(uSeed));
    float rune2 = snoise(p * 8.0 + vec3(uSeed * 5.0));
    float lines = abs(sin(rune1 * 6.28 + rune2 * 3.14));
    pattern = smoothstep(0.85, 0.95, lines) * 0.25;
  }
  // Prismatic (7)
  else {
    float prism = snoise(p * 6.0 + uTime * 0.02 + vec3(uSeed));
    pattern = prism * 0.5 + 0.5;
    pattern *= 0.2;
  }

  return pattern;
}

void main() {
  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 N = normalize(vNormal);
  float NdV = max(dot(N, V), 0.0);

  // ── Lighting ──
  vec3 keyDir = normalize(vec3(2.0, 5.0, 4.0));
  float keyDiff = dot(N, keyDir) * 0.5 + 0.5;
  vec3 diffuse = uBaseColor * keyDiff * keyDiff * 0.65;

  vec3 fillDir = normalize(vec3(-3.0, 2.0, -1.0));
  float fillDiff = dot(N, fillDir) * 0.5 + 0.5;
  diffuse += uBaseColor * fillDiff * 0.25;

  float hem = N.y * 0.5 + 0.5;
  vec3 ambient = uBaseColor * mix(0.18, 0.32, hem);

  // ── Scale pattern ──
  float pattern = scalePattern(vLocalPos, uScaleType);
  // During generating phase, scales glow with light seeping through
  float scaleGlow = pattern * uGrowth * 0.5;
  vec3 patternColor = mix(uBaseColor * (1.0 + pattern * 0.5), uCoreColor, scaleGlow);

  // ── Subsurface scattering ──
  float sss = pow(1.0 - NdV, 2.5);
  vec3 sssGlow = uCoreColor * 0.3 * sss * (0.5 + uGrowth * 0.3);

  // ── Heart glow ──
  float pulse = uBeat;
  float breath = sin(uTime * 0.4) * 0.5 + 0.5;
  float baseIntensity = 0.15 + breath * 0.08 + pulse * 0.25;
  float coreIntensity = baseIntensity + uGrowth * (0.8 + pulse * 0.4);

  float glow = pow(NdV, 2.0);
  float hotspot = pow(NdV, 10.0);
  vec3 core = mix(uCoreColor * 0.3, uCoreColor, hotspot);

  // ── Mist / rim ──
  float fresnel = pow(1.0 - NdV, 3.0);
  float mistNoise = snoise(vWorldPos * 2.0 + uTime * 0.15 + vec3(uSeed)) * 0.5 + 0.5;
  float mistAmount = uMistIntensity / 4.0; // normalize to 0..1
  vec3 mist = uCoreColor * fresnel * mistAmount * (0.5 + mistNoise * 0.5);

  // During generating phase, mist intensifies regardless of attribute
  float genMist = max(0.0, uGrowth - 1.0) * 0.4;
  mist += uCoreColor * fresnel * genMist * mistNoise;

  // ── Fresnel rim ──
  vec3 rim = (uBaseColor * 0.3 + vec3(0.05)) * fresnel * (1.0 - mistAmount * 0.5);

  // ── Specular ──
  vec3 H1 = normalize(keyDir + V);
  float spec = pow(max(dot(N, H1), 0.0), 80.0) * 0.45;

  // ── Compose ──
  vec3 color = ambient + diffuse;
  color = mix(color, patternColor, pattern);
  color += sssGlow;
  color += rim;
  color += mist;
  color += core * glow * coreIntensity;
  color += uSpecColor * spec;

  // Reinhard tone mapping
  color = color / (color + vec3(1.0));

  // ── Dissolve ──
  float dissolveNoise = snoise(vLocalPos * 5.0 + vec3(uSeed * 11.0));
  float dissolveThreshold = uDissolve * 2.0 - 1.0;
  if (dissolveNoise < dissolveThreshold) discard;

  // Edge glow on dissolve
  float edgeDist = dissolveNoise - dissolveThreshold;
  if (edgeDist < 0.15 && uDissolve > 0.0) {
    color += uCoreColor * 2.0 * (1.0 - edgeDist / 0.15);
  }

  gl_FragColor = vec4(color, 1.0);
}
`

export const EGG_GLOW_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

export const EGG_GLOW_FRAG = /* glsl */ `
varying vec2 vUv;
uniform float uTime;
uniform float uGrowth;
uniform float uDissolve;
uniform vec3 uGlowColor;
uniform float uMistIntensity;

void main() {
  vec2 center = vUv - 0.5;
  float d = length(center);

  float glow = exp(-d * 3.5) * 0.2;
  float pulse = pow(max(0.0, sin(uTime * (1.0 + uGrowth * 1.5))), 8.0);
  float breath = sin(uTime * 0.4) * 0.5 + 0.5;
  float intensity = (0.15 + breath * 0.06 + pulse * 0.1) + uGrowth * 0.6;

  // Mist adds to glow
  intensity += uMistIntensity / 4.0 * 0.3;

  vec3 color = mix(uGlowColor * 0.5, uGlowColor, breath) * glow * intensity;
  float alpha = glow * intensity * (1.0 - uDissolve);
  gl_FragColor = vec4(color, alpha);
}
`

export const SHADOW_VERT = /* glsl */ `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`

export const SHADOW_FRAG = /* glsl */ `
varying vec2 vUv;
void main() {
  float d = length(vUv - 0.5) * 2.0;
  float alpha = 0.35 * (1.0 - smoothstep(0.3, 1.0, d));
  vec3 shadowColor = mix(vec3(0.04, 0.02, 0.03), vec3(0.0), d * 0.5);
  gl_FragColor = vec4(shadowColor, alpha);
}
`
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hatch/eggShaders.ts
git commit -m "feat: add egg GLSL shaders with shape displacement, scale patterns, heart glow, mist"
```

---

## Task 3: Extract PetReveal Component

**Files:**
- Create: `frontend/src/components/hatch/PetReveal.tsx`

- [ ] **Step 1: Create PetReveal.tsx**

Extract the PetReveal component from `BlobScene.tsx` (lines 237–308) into its own file, unchanged:

```tsx
import { useRef, useMemo } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'

export default function PetReveal({ voxels, progress }: {
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
  progress: number
}) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const groupRef = useRef<THREE.Group>(null)
  const timeRef = useRef(0)

  const centered = useMemo(() => {
    if (voxels.length === 0) return voxels
    const cx = voxels.reduce((s, v) => s + v.x, 0) / voxels.length
    const cy = voxels.reduce((s, v) => s + v.y, 0) / voxels.length
    const cz = voxels.reduce((s, v) => s + v.z, 0) / voxels.length
    return voxels.map(v => ({ ...v, x: v.x - cx, y: v.y - cy, z: v.z - cz }))
  }, [voxels])

  useFrame((_, delta) => {
    timeRef.current += delta
    if (!meshRef.current || !groupRef.current) return
    const mesh = meshRef.current
    const obj = new THREE.Object3D()
    const col = new THREE.Color()
    const show = Math.floor(progress * centered.length)

    for (let i = 0; i < centered.length; i++) {
      const v = centered[i]
      if (i < show) {
        const localP = Math.min(1, (progress * centered.length - i) / 5)
        const ease = 1 - Math.pow(1 - localP, 3)
        obj.position.set(
          v.x * 3 * (1 - ease) + v.x * ease,
          v.y * 3 * (1 - ease) + 5 * (1 - ease) + v.y * ease,
          v.z * 3 * (1 - ease) + v.z * ease
        )
        const scale = ease * (localP < 0.3 ? localP / 0.3 : 1)
        obj.scale.setScalar(scale)
        obj.updateMatrix()
        mesh.setMatrixAt(i, obj.matrix)
        const cb = Math.min(1, localP * 2)
        const glow = (1 - cb) * 2
        col.setRGB(
          (v.r / 255) * cb + glow,
          (v.g / 255) * cb + glow,
          (v.b / 255) * cb + glow
        )
        mesh.setColorAt(i, col)
      } else {
        obj.scale.setScalar(0)
        obj.updateMatrix()
        mesh.setMatrixAt(i, obj.matrix)
      }
    }

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
    groupRef.current.rotation.y += delta * 0.4
  })

  if (centered.length === 0) return null

  return (
    <group ref={groupRef} position={[0, 3, 0]}>
      <pointLight color="#ffffff" intensity={8} distance={25} decay={2} />
      <pointLight color="#999999" intensity={4} distance={20} decay={2} position={[0, -3, 0]} />
      <pointLight color="#ffffff" intensity={3} distance={15} decay={2} position={[0, 5, 5]} />
      <instancedMesh ref={meshRef} args={[undefined, undefined, centered.length]} frustumCulled={false}>
        <boxGeometry args={[0.9, 0.9, 0.9]} />
        <meshBasicMaterial vertexColors toneMapped={false} fog={false} />
      </instancedMesh>
    </group>
  )
}
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hatch/PetReveal.tsx
git commit -m "refactor: extract PetReveal into standalone component"
```

---

## Task 4: EggScene Component

**Files:**
- Create: `frontend/src/components/hatch/EggScene.tsx`

- [ ] **Step 1: Create EggScene.tsx**

This is the main R3F scene — egg mesh, glow halo, ground shadow, camera controller, and pet reveal. It replaces BlobScene.tsx.

```tsx
import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { EGG_VERT, EGG_FRAG, EGG_GLOW_VERT, EGG_GLOW_FRAG, SHADOW_VERT, SHADOW_FRAG } from './eggShaders'
import PetReveal from './PetReveal'
import type { Phase, EggProfile } from './types'

// ── Color map for egg color attribute ──

const COLOR_MAP: Record<string, { base: [number, number, number]; core: [number, number, number]; spec: [number, number, number] }> = {
  Stone:      { base: [0.55, 0.52, 0.48], core: [0.65, 0.6, 0.55],  spec: [0.9, 0.88, 0.85] },
  Moss:       { base: [0.42, 0.55, 0.38], core: [0.3, 0.6, 0.25],   spec: [0.8, 0.9, 0.75] },
  Amber:      { base: [0.78, 0.58, 0.32], core: [0.85, 0.55, 0.12], spec: [1.0, 0.9, 0.7] },
  Cobalt:     { base: [0.32, 0.48, 0.72], core: [0.22, 0.38, 0.82], spec: [0.7, 0.8, 1.0] },
  Crimson:    { base: [0.75, 0.28, 0.25], core: [0.85, 0.18, 0.12], spec: [1.0, 0.7, 0.7] },
  Violet:     { base: [0.55, 0.35, 0.68], core: [0.55, 0.22, 0.75], spec: [0.85, 0.7, 1.0] },
  Obsidian:   { base: [0.15, 0.14, 0.18], core: [0.3, 0.25, 0.4],   spec: [0.6, 0.55, 0.7] },
  Iridescent: { base: [0.6, 0.5, 0.65],   core: [0.7, 0.4, 0.8],   spec: [1.0, 0.9, 1.0] },
}

const SIZE_SCALE_MAP: Record<string, number> = {
  Tiny: 0.6, Small: 0.8, Standard: 1.0, Large: 1.2, Massive: 1.4, Colossal: 1.7,
}

function getEggUniforms(egg: EggProfile) {
  const colorAttr = egg.attributes.find(a => a.category === 'color')
  const colors = COLOR_MAP[colorAttr?.option.name || 'Stone'] || COLOR_MAP.Stone
  const shapeAttr = egg.attributes.find(a => a.category === 'shape')
  const scaleAttr = egg.attributes.find(a => a.category === 'scales')
  const sizeAttr = egg.attributes.find(a => a.category === 'size')
  const mistAttr = egg.attributes.find(a => a.category === 'mist')

  return {
    shapeType: shapeAttr?.option.value ?? 0,
    scaleType: scaleAttr?.option.value ?? 0,
    sizeScale: SIZE_SCALE_MAP[sizeAttr?.option.name || 'Standard'] || 1.0,
    mistIntensity: mistAttr?.option.value ?? 0,
    baseColor: colors.base,
    coreColor: colors.core,
    specColor: colors.spec,
  }
}

// ── Glow Halo ──

function GlowHalo({ phase, glowColor, mistIntensity }: { phase: Phase; glowColor: [number, number, number]; mistIntensity: number }) {
  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uGrowth: { value: 0 },
      uDissolve: { value: 0 },
      uGlowColor: { value: new THREE.Vector3(...glowColor) },
      uMistIntensity: { value: mistIntensity },
    },
    vertexShader: EGG_GLOW_VERT,
    fragmentShader: EGG_GLOW_FRAG,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
  }), [glowColor, mistIntensity])

  useFrame((_, dt) => {
    mat.uniforms.uTime.value += dt
    let targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 2.0
    mat.uniforms.uGrowth.value += (targetGrowth - mat.uniforms.uGrowth.value) * 0.03
    if (phase === 'reveal') {
      mat.uniforms.uDissolve.value = Math.min(1, mat.uniforms.uDissolve.value + dt * 0.7)
    }
  })

  return (
    <mesh position={[0, 0, -0.5]} material={mat}>
      <planeGeometry args={[6, 6]} />
    </mesh>
  )
}

// ── Egg Mesh ──

function EggMesh({ phase, egg, mouseRef }: {
  phase: Phase
  egg: EggProfile
  mouseRef: React.MutableRefObject<{ x: number; y: number }>
}) {
  const groupRef = useRef<THREE.Group>(null)
  const dissolveRef = useRef(0)
  const timeRef = useRef(0)
  const growthRef = useRef(0)

  const uniforms = useMemo(() => getEggUniforms(egg), [egg])

  const mat = useMemo(() => new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uGrowth: { value: 0 },
      uDissolve: { value: 0 },
      uBeat: { value: 0 },
      uSeed: { value: Math.random() * 100 },
      uShapeType: { value: uniforms.shapeType },
      uScaleType: { value: uniforms.scaleType },
      uSizeScale: { value: uniforms.sizeScale },
      uMistIntensity: { value: uniforms.mistIntensity },
      uBaseColor: { value: new THREE.Vector3(...uniforms.baseColor) },
      uCoreColor: { value: new THREE.Vector3(...uniforms.coreColor) },
      uSpecColor: { value: new THREE.Vector3(...uniforms.specColor) },
    },
    vertexShader: EGG_VERT,
    fragmentShader: EGG_FRAG,
    transparent: true,
  }), [uniforms])

  useFrame((_, dt) => {
    timeRef.current += dt
    const t = timeRef.current
    mat.uniforms.uTime.value = t

    // Growth targets per phase
    let targetGrowth = 0
    if (phase === 'idle') targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 2.0
    growthRef.current += (targetGrowth - growthRef.current) * 0.03
    mat.uniforms.uGrowth.value = growthRef.current

    // Dissolve
    if (phase === 'reveal') {
      dissolveRef.current = Math.min(1, dissolveRef.current + dt * 0.5)
    }
    mat.uniforms.uDissolve.value = dissolveRef.current

    // Heartbeat — faster with growth
    const beatSpeed = 1.0 + growthRef.current * 1.5
    const pulse = Math.pow(Math.max(0, Math.sin(t * beatSpeed)), 8.0)
    mat.uniforms.uBeat.value = pulse

    // Group scale with heartbeat
    const beatAmp = 0.08 + growthRef.current * 0.06
    const scale = 1.0 + pulse * beatAmp

    if (groupRef.current) {
      groupRef.current.scale.setScalar(scale)
      groupRef.current.rotation.y += dt * 0.15 + mouseRef.current.x * 0.01
      groupRef.current.rotation.x = mouseRef.current.y * 0.1
    }
  })

  if (dissolveRef.current >= 0.99) return null

  return (
    <group ref={groupRef}>
      <mesh material={mat}>
        <sphereGeometry args={[1, 64, 64]} />
      </mesh>
    </group>
  )
}

// ── Ground Shadow ──

function GroundShadow() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.2, 0]}>
      <circleGeometry args={[1.5, 64]} />
      <shaderMaterial
        vertexShader={SHADOW_VERT}
        fragmentShader={SHADOW_FRAG}
        transparent
        depthWrite={false}
      />
    </mesh>
  )
}

// ── Camera ──

function SceneCamera({ phase }: { phase: Phase }) {
  const { camera } = useThree()
  const timeRef = useRef(0)

  useFrame((_, dt) => {
    timeRef.current += dt
    const t = timeRef.current

    if (phase === 'idle' || phase === 'hatching' || phase === 'stats') {
      // Gentle orbit around egg
      const cx = Math.sin(t * 0.08) * 0.3
      const cy = 0.5 + Math.sin(t * 0.06) * 0.2
      const cz = phase === 'idle' ? 5 : 4
      camera.position.lerp(new THREE.Vector3(cx, cy, cz), 0.02)
      camera.lookAt(0, 0, 0)
    } else if (phase === 'generating') {
      // Pull in closer
      const cx = Math.sin(t * 0.1) * 0.4
      const cy = 0.3 + Math.sin(t * 0.08) * 0.3
      camera.position.lerp(new THREE.Vector3(cx, cy, 3.5), 0.02)
      camera.lookAt(0, 0, 0)
    } else if (phase === 'reveal') {
      // Pull back to show creature
      camera.position.lerp(new THREE.Vector3(0, 3, 11), 0.03)
      camera.lookAt(0, 1, 0)
    }
  })

  return null
}

// ── Main Scene (exported) ──

export default function EggScene({ phase, egg, revealProgress, voxels }: {
  phase: Phase
  egg: EggProfile
  revealProgress: number
  voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[]
}) {
  const mouseRef = useRef({ x: 0, y: 0 })
  const uniforms = useMemo(() => getEggUniforms(egg), [egg])

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mouseRef.current.x = (e.clientX / window.innerWidth) * 2 - 1
      mouseRef.current.y = (e.clientY / window.innerHeight) * 2 - 1
    }
    window.addEventListener('mousemove', onMove)
    return () => window.removeEventListener('mousemove', onMove)
  }, [])

  return (
    <Canvas
      camera={{ position: [0, 0.5, 5], fov: 35, near: 0.1, far: 100 }}
      gl={{ antialias: true, alpha: false }}
      className="!absolute inset-0"
    >
      <color attach="background" args={['#0a0a0f']} />
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 5, 5]} intensity={0.5} />

      <SceneCamera phase={phase} />
      <GlowHalo phase={phase} glowColor={uniforms.coreColor} mistIntensity={uniforms.mistIntensity} />
      <EggMesh phase={phase} egg={egg} mouseRef={mouseRef} />
      <GroundShadow />

      {phase === 'reveal' && voxels.length > 0 && (
        <PetReveal voxels={voxels} progress={revealProgress} />
      )}
    </Canvas>
  )
}
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hatch/EggScene.tsx
git commit -m "feat: add EggScene component with 3D egg renderer"
```

---

## Task 5: Egg Tooltip Component

**Files:**
- Create: `frontend/src/components/hatch/EggTooltip.tsx`

- [ ] **Step 1: Create EggTooltip.tsx**

```tsx
import { rarityColors } from '../../data/rarity'
import type { EggProfile, RolledAttribute } from './types'
import { TIER_POINTS } from './eggAttributes'

const STAT_BIAS_LABELS: Record<string, string[]> = {
  shape:  ['resilience', 'energy'],
  scales: ['focus', 'creativity'],
  color:  ['social', 'humor'],
  size:   ['energy', 'resilience'],
  mist:   ['curiosity', 'creativity'],
}

const TIER_COLORS: Record<string, string> = {
  common: '#9ca3af',
  uncommon: '#22c55e',
  rare: '#3b82f6',
  legendary: '#a855f7',
  mythic: '#ec4899',
}

function AttributeRow({ attr }: { attr: RolledAttribute }) {
  const tierColor = TIER_COLORS[attr.option.tier] || '#9ca3af'
  const biases = STAT_BIAS_LABELS[attr.category] || []

  return (
    <div className="flex items-center justify-between gap-4 py-1">
      <div className="flex items-center gap-2">
        <span className="text-white/40 text-xs capitalize w-12">{attr.category}</span>
        <span className="text-white text-xs font-medium">{attr.option.name}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs" style={{ color: tierColor }}>{attr.option.tier}</span>
        {biases.length > 0 && (
          <span className="text-white/25 text-[10px]">
            +{biases.join(', +')}
          </span>
        )}
      </div>
    </div>
  )
}

export default function EggTooltip({ egg, visible }: { egg: EggProfile; visible: boolean }) {
  if (!visible) return null

  return (
    <div
      className="absolute top-4 right-4 z-20 w-64 rounded-2xl p-4 space-y-2"
      style={{
        background: 'rgba(15, 15, 20, 0.9)',
        backdropFilter: 'blur(30px)',
        WebkitBackdropFilter: 'blur(30px)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: '0 12px 40px rgba(0, 0, 0, 0.3)',
        animation: 'fadeUp 0.3s ease-out',
      }}
    >
      <div className="text-center pb-2 border-b border-white/10">
        <div className="text-white text-sm font-medium tracking-wide">{egg.name}</div>
        <div className="text-xs mt-1" style={{ color: rarityColors[egg.rarity] }}>
          {egg.rarity.toUpperCase()} — {egg.totalPoints.toFixed(1)} / 10
        </div>
      </div>

      <div className="space-y-0.5">
        {egg.attributes.map(attr => (
          <AttributeRow key={attr.category} attr={attr} />
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hatch/EggTooltip.tsx
git commit -m "feat: add EggTooltip hover card component"
```

---

## Task 6: Update StatsCard with Quality Badge

**Files:**
- Modify: `frontend/src/components/hatch/StatsCard.tsx`

- [ ] **Step 1: Add QualityBadge to StatsCard.tsx**

Add the following component at the end of the file, after the `RarityBadge` component:

```tsx
export function QualityBadge({ quality, visible }: { quality: QualityTier; visible: boolean }) {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (visible) { const t = setTimeout(() => setShow(true), 300); return () => clearTimeout(t) }
  }, [visible])

  if (!visible || quality === 'neutral') return null

  const isEnhanced = quality === 'enhanced'
  const color = isEnhanced ? '#fbbf24' : '#6b7280'
  const label = isEnhanced ? 'ENHANCED' : 'FRACTURED'

  return (
    <div
      className="text-center pt-1"
      style={{
        opacity: show ? 1 : 0,
        transform: show ? 'scale(1)' : 'scale(0.8)',
        transition: 'all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)',
      }}
    >
      <div
        className="inline-block px-4 py-1.5 rounded-full text-xs font-bold tracking-widest"
        style={{
          backgroundColor: `${color}15`,
          color,
          border: `1px solid ${color}40`,
          boxShadow: isEnhanced ? `0 0 16px ${color}20` : 'none',
        }}
      >
        {label}
      </div>
    </div>
  )
}
```

Also add the import for `QualityTier` at the top of the file:

```typescript
import type { QualityTier } from './types'
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hatch/StatsCard.tsx
git commit -m "feat: add QualityBadge component (Enhanced/Fractured)"
```

---

## Task 7: Update gameLogic.ts

**Files:**
- Modify: `frontend/src/components/hatch/gameLogic.ts`

- [ ] **Step 1: Replace gameLogic.ts**

Replace the entire file. The new version delegates to eggAttributes for rolling and keeps GEN_STATUS and readPendingPet:

```typescript
import type { EggProfile } from './types'

export { rollEgg, rollStatsFromEgg, computeQuality, STAT_NAMES } from './eggAttributes'

export const GEN_STATUS = [
  { t: 0, text: 'Creating your companion...' },
  { t: 5, text: 'Shaping consciousness...' },
  { t: 10, text: 'Building its world...' },
  { t: 18, text: 'Almost ready...' },
]

export function readPendingEgg(): { egg: EggProfile; stats: Record<string, number>; quality: string } | null {
  try {
    const raw = localStorage.getItem('pendingEgg')
    if (!raw) return null
    return JSON.parse(raw)
  } catch {
    return null
  }
}
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/hatch/gameLogic.ts
git commit -m "refactor: replace old roll/rarity logic with egg-based system"
```

---

## Task 8: Rewrite Hatch Page

**Files:**
- Modify: `frontend/src/pages/Hatch.tsx`

- [ ] **Step 1: Replace Hatch.tsx**

Replace the entire file with the new egg-based flow:

```tsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { supabase } from '../lib/supabase'
import EggScene from '../components/hatch/EggScene'
import EggTooltip from '../components/hatch/EggTooltip'
import { StatBar, TotalReveal, RarityBadge, QualityBadge } from '../components/hatch/StatsCard'
import { rollEgg, rollStatsFromEgg, computeQuality, GEN_STATUS, readPendingEgg, STAT_NAMES } from '../components/hatch/gameLogic'
import { rarityColors } from '../data/rarity'
import type { Phase, PetData, HatchProps, EggProfile, QualityTier } from '../components/hatch/types'

export default function Hatch({ onHatch, onComplete, session }: HatchProps) {
  // ── Egg state ──
  const [egg, setEgg] = useState<EggProfile>(() => rollEgg())
  const [phase, setPhase] = useState<Phase>('idle')
  const [hovering, setHovering] = useState(false)

  // ── Stats state ──
  const [rolledStats, setRolledStats] = useState<Record<string, number> | null>(null)
  const [quality, setQuality] = useState<QualityTier>('neutral')
  const [statsRevealed, setStatsRevealed] = useState(false)

  // ── Reveal state ──
  const [revealProgress, setRevealProgress] = useState(0)
  const [petData, setPetData] = useState<PetData | null>(null)
  const [fullPetResponse, setFullPetResponse] = useState<any>(null)
  const [backstoryText, setBackstoryText] = useState('')
  const [showBeginButton, setShowBeginButton] = useState(false)
  const [flashActive, setFlashActive] = useState(false)

  // ── Generating state ──
  const [genElapsed, setGenElapsed] = useState(0)
  const genStartRef = useRef(0)
  const genFrameRef = useRef(0)
  const revealFrameRef = useRef(0)

  // ── Phase: Idle → Hatching ──
  const startHatching = useCallback(() => {
    const stats = rollStatsFromEgg(egg)
    const q = computeQuality(stats, egg)
    setRolledStats(stats)
    setQuality(q)
    setPhase('hatching')

    // After growth animation, show stats
    setTimeout(() => {
      setPhase('stats')
      setStatsRevealed(true)
    }, 2000)
  }, [egg])

  // ── Phase: Stats → Generating (after sign-in) ──
  const startGenerating = useCallback(async () => {
    if (!rolledStats) return
    setPhase('generating')
    genStartRef.current = Date.now()

    const response = await onHatch(rolledStats, egg.rarity)
    if (response) {
      setFullPetResponse(response)
      setPetData({
        id: response.id, name: response.name, rarity: response.rarity,
        stats: response.stats, backstory: response.backstory, voxels: response.voxels || [],
      })
    } else {
      setPetData({
        id: 'fallback', name: 'Unknown', rarity: egg.rarity,
        stats: rolledStats,
        backstory: 'A creature emerged from the void with wonder in its eyes.',
        voxels: [{ x: 0, y: 0, z: 0, r: 255, g: 255, b: 255 }],
      })
    }

    // Trigger reveal
    setFlashActive(true)
    setTimeout(() => setFlashActive(false), 800)
    setTimeout(() => {
      setPhase('reveal')
      const start = Date.now()
      const animate = () => {
        const p = Math.min((Date.now() - start) / 4000, 1)
        setRevealProgress(p)
        if (p < 1) {
          revealFrameRef.current = requestAnimationFrame(animate)
        } else {
          setTimeout(() => setStatsRevealed(true), 600)
        }
      }
      revealFrameRef.current = requestAnimationFrame(animate)
    }, 500)
  }, [rolledStats, egg, onHatch])

  // ── Auto-generate if signed in during stats phase ──
  useEffect(() => {
    if (phase !== 'stats' || !session || !rolledStats) return
    const timer = setTimeout(() => startGenerating(), 1500)
    return () => clearTimeout(timer)
  }, [phase, session, rolledStats, startGenerating])

  // ── Sign-in with pending egg ──
  const signInWithGoogle = async () => {
    if (rolledStats) {
      localStorage.setItem('pendingEgg', JSON.stringify({ egg, stats: rolledStats, quality }))
    }
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/hatch' },
    })
  }

  // ── OAuth return with pending egg ──
  useEffect(() => {
    if (!session) return
    const pending = readPendingEgg()
    if (pending) {
      localStorage.removeItem('pendingEgg')
      setEgg(pending.egg)
      setRolledStats(pending.stats)
      setQuality(pending.quality as QualityTier)
      setPhase('stats')
      setStatsRevealed(true)
      setTimeout(() => startGenerating(), 500)
    }
  }, [session, startGenerating])

  // ── Generating elapsed timer ──
  useEffect(() => {
    if (phase !== 'generating') return
    genStartRef.current = Date.now()
    const tick = () => {
      setGenElapsed((Date.now() - genStartRef.current) / 1000)
      genFrameRef.current = requestAnimationFrame(tick)
    }
    genFrameRef.current = requestAnimationFrame(tick)
    return () => { if (genFrameRef.current) cancelAnimationFrame(genFrameRef.current) }
  }, [phase])

  // ── Backstory typewriter ──
  useEffect(() => {
    if (phase !== 'reveal' || !petData) return
    const delay = STAT_NAMES.length * 200 + 2000
    const startTimer = setTimeout(() => {
      let i = 0
      const iv = setInterval(() => {
        i++
        setBackstoryText(petData.backstory.slice(0, i))
        if (i >= petData.backstory.length) { clearInterval(iv); setTimeout(() => setShowBeginButton(true), 500) }
      }, 25)
      return () => clearInterval(iv)
    }, delay)
    return () => clearTimeout(startTimer)
  }, [phase, petData])

  // ── Cleanup ──
  useEffect(() => {
    return () => {
      if (genFrameRef.current) cancelAnimationFrame(genFrameRef.current)
      if (revealFrameRef.current) cancelAnimationFrame(revealFrameRef.current)
    }
  }, [])

  const genStatusText = GEN_STATUS.reduce((msg, s) => genElapsed >= s.t ? s.text : msg, GEN_STATUS[0].text)
  const statEntries = rolledStats ? Object.entries(rolledStats) : []
  const total = rolledStats ? Object.values(rolledStats).reduce((a, b) => a + b, 0) : 0

  return (
    <div
      className="min-h-screen bg-[#0a0a0f] relative overflow-hidden"
      onMouseEnter={() => setHovering(true)}
      onMouseLeave={() => setHovering(false)}
    >
      {/* ── 3D Scene ── */}
      <div className="absolute inset-0 z-0">
        <EggScene
          phase={phase}
          egg={egg}
          revealProgress={revealProgress}
          voxels={petData?.voxels || []}
        />
      </div>

      {/* ── Flash ── */}
      {flashActive && (
        <div className="absolute inset-0 z-50 bg-white/30" style={{ animation: 'flashOut 0.8s ease-out forwards' }} />
      )}

      {/* ── Egg info (always visible) ── */}
      {phase !== 'reveal' && (
        <div className="fixed top-20 left-0 right-0 z-10 text-center" style={{ animation: 'fadeUp 0.6s ease-out' }}>
          <h2 className="text-xl font-light text-white tracking-wide">{egg.name}</h2>
          <div className="mt-2 flex items-center justify-center gap-3">
            <RarityBadge rarity={egg.rarity} visible={true} />
            <span className="text-white/30 text-xs">{egg.totalPoints.toFixed(1)} / 10</span>
          </div>
        </div>
      )}

      {/* ── Tooltip (on hover) ── */}
      <EggTooltip egg={egg} visible={hovering && (phase === 'idle' || phase === 'hatching')} />

      {/* ── Idle: Hatch button ── */}
      {phase === 'idle' && (
        <div className="fixed bottom-16 left-0 right-0 z-10 flex flex-col items-center" style={{ animation: 'fadeUp 0.6s ease-out 0.3s both' }}>
          <button
            onClick={startHatching}
            className="group px-12 py-4 bg-white text-black text-sm font-medium tracking-[0.15em] uppercase
              rounded-xl hover:bg-gray-100 transition-all active:scale-[0.97]
              shadow-[0_4px_24px_rgba(255,255,255,0.1)] hover:shadow-[0_8px_32px_rgba(255,255,255,0.2)]"
          >
            <span className="inline-flex items-center gap-2">
              Hatch
              <svg className="w-4 h-4 transition-transform group-hover:translate-x-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </span>
          </button>
        </div>
      )}

      {/* ── Stats phase: stats card ── */}
      {(phase === 'stats' || phase === 'generating') && rolledStats && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-md px-6 z-10"
          style={{ animation: 'fadeUp 0.6s ease-out' }}
        >
          <div
            className="rounded-[24px] p-6 space-y-3"
            style={{
              background: 'rgba(15, 15, 20, 0.85)',
              backdropFilter: 'blur(40px)',
              WebkitBackdropFilter: 'blur(40px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: '0 16px 48px rgba(0, 0, 0, 0.3)',
            }}
          >
            <div className="space-y-2">
              {statEntries.map(([name, value], i) => (
                <StatBar key={name} name={name} value={value} delay={i * 200} revealed={statsRevealed} />
              ))}
            </div>

            <TotalReveal total={total} visible={statsRevealed} />
            <QualityBadge quality={quality} visible={statsRevealed} />

            {/* Sign-in button (if not signed in) */}
            {phase === 'stats' && !session && (
              <div className="pt-3 space-y-3" style={{ animation: 'fadeUp 0.5s ease-out 1.5s both' }}>
                <p className="text-center text-white/40 text-xs tracking-wide">
                  sign in to hatch your egg
                </p>
                <button
                  onClick={signInWithGoogle}
                  className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-white text-black text-sm font-medium tracking-wide rounded-xl hover:bg-gray-100 transition-colors"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                  </svg>
                  Continue with Google
                </button>
              </div>
            )}

            {/* Generating status */}
            {phase === 'generating' && (
              <div className="text-center pt-2">
                <p className="text-white/40 text-xs tracking-[0.2em] uppercase animate-pulse">{genStatusText}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Reveal: creature card ── */}
      {phase === 'reveal' && petData && (
        <div
          className="fixed bottom-6 left-1/2 -translate-x-1/2 w-full max-w-lg px-6 z-10"
          style={{ animation: 'fadeUp 0.8s ease-out 2s both' }}
        >
          <div
            className="rounded-[24px] p-6 space-y-4"
            style={{
              background: 'rgba(15, 15, 20, 0.85)',
              backdropFilter: 'blur(40px)',
              WebkitBackdropFilter: 'blur(40px)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              boxShadow: '0 16px 48px rgba(0, 0, 0, 0.3)',
            }}
          >
            <div className="text-center space-y-2">
              <h2 className="text-2xl font-light text-white tracking-wide">{petData.name}</h2>
              <RarityBadge rarity={petData.rarity} visible={true} />
            </div>

            <div className="space-y-2 pt-2 border-t border-white/10">
              {Object.entries(petData.stats).map(([s, v], i) => (
                <StatBar key={s} name={s} value={v} delay={i * 200 + 500} revealed={statsRevealed} />
              ))}
            </div>

            <TotalReveal
              total={Object.values(petData.stats).reduce((a, b) => a + b, 0)}
              visible={statsRevealed}
            />

            {backstoryText && (
              <div className="pt-2 border-t border-white/10">
                <p className="text-white/50 text-sm leading-relaxed font-light">
                  {backstoryText}
                  {backstoryText.length < petData.backstory.length && (
                    <span className="text-white/30 animate-pulse">|</span>
                  )}
                </p>
              </div>
            )}

            {showBeginButton && (
              <button
                onClick={() => fullPetResponse ? onComplete(fullPetResponse) : onComplete(petData)}
                className="w-full py-3 bg-white text-neutral-900 font-medium rounded-xl
                  hover:bg-white/90 transition-all text-sm tracking-wider uppercase active:scale-[0.98]"
                style={{ animation: 'fadeUp 0.5s ease-out' }}
              >
                Begin Journey
              </button>
            )}
          </div>
        </div>
      )}

      <style>{`
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes flashOut {
          0% { opacity: 1; }
          100% { opacity: 0; }
        }
        .stat-shimmer {
          animation: shimmerSweep 0.6s ease-out forwards;
        }
        @keyframes shimmerSweep {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        .mythic-badge {
          background: linear-gradient(90deg, #ec4899, #8b5cf6, #3b82f6, #22c55e, #eab308, #ec4899);
          background-size: 300% 100%;
          animation: rainbow 3s linear infinite;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          border: 1px solid rgba(236, 72, 153, 0.3);
        }
        @keyframes rainbow {
          from { background-position: 0% 50%; }
          to { background-position: 300% 50%; }
        }
      `}</style>
    </div>
  )
}
```

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Visual verification**

Run: `cd frontend && npm run dev`
Open in browser. Expected:
- Dark background with 3D egg rendering
- Egg name + rarity badge visible at top
- Hovering shows tooltip with attribute breakdown
- "Hatch" button at bottom
- Clicking Hatch → egg grows → stats animate in → quality badge appears

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Hatch.tsx
git commit -m "feat: rewrite Hatch page with egg rarity system"
```

---

## Task 9: Remove Old Files & Clean Up

**Files:**
- Remove: `frontend/src/components/hatch/BlobScene.tsx`
- Remove: `frontend/src/components/hatch/shaders.ts`
- Remove: `frontend/src/components/hatch/presets.ts`
- Remove: `frontend/src/pages/Landing.tsx`

- [ ] **Step 1: Delete old files**

```bash
rm frontend/src/components/hatch/BlobScene.tsx
rm frontend/src/components/hatch/shaders.ts
rm frontend/src/components/hatch/presets.ts
rm frontend/src/pages/Landing.tsx
```

- [ ] **Step 2: Verify no remaining imports reference deleted files**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors. If any file still imports from deleted modules, fix those imports.

- [ ] **Step 3: Build verification**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 4: Commit**

```bash
git add -u
git commit -m "chore: remove BlobScene, old shaders, presets, and unused Landing page"
```

---

## Task 10: Final Integration Test

- [ ] **Step 1: Full flow test in browser**

Run: `cd frontend && npm run dev`

Test the complete flow:
1. Page loads → egg appears with name + rarity above
2. Hover → tooltip shows all 5 attributes with tiers
3. Click Hatch → egg grows, heart beats faster
4. Stats animate in one by one → quality badge shows
5. Sign-in button appears (if not signed in)
6. After sign-in → generating phase → egg keeps growing with scale glow
7. LLM returns → flash → egg dissolves → voxel creature assembles
8. Full profile card with backstory typewriter → "Begin Journey" button

- [ ] **Step 2: Build succeeds**

Run: `cd frontend && npm run build`
Expected: Clean build, no errors

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: integration fixes for egg rarity system"
```
