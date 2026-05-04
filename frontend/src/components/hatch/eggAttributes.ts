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

  for (const stat of STAT_NAMES) {
    ranges[stat] = [1, 6]
  }

  for (const attr of attributes) {
    const biasedStats = STAT_BIASES[attr.category] || []
    const tierBonus = TIER_POINTS[attr.option.tier]
    for (const stat of biasedStats) {
      const [min, max] = ranges[stat]
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
