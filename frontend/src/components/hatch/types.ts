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
