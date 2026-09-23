import registry from '../../../shared/blocks.json'

export type Layer = 'opaque' | 'cutout' | 'translucent' | 'none'
export type Rgb = [number, number, number]

export interface TileRecipe {
  pattern: string
  color: Rgb
  accent?: Rgb
  /** Growth stage for crop sprites, 1 (just planted) to 4 (ripe). */
  size?: number
}

export interface FaceTextures {
  top: string
  side: string
  bottom: string
}

export interface BlockDef {
  id: number
  name: string
  color: Rgb
  layer: Layer
  solid: boolean
  textures: FaceTextures
  glow: boolean
  fluid: boolean
}

interface RawBlock {
  name: string
  color: number[]
  textures: string | FaceTextures
  layer: Layer
  solid: boolean
  glow?: boolean
  fluid?: boolean
}

export const AIR = 0
/** Client-only id for material names the registry does not know. */
export const MISSING_ID = 255

export const TILES = registry.tiles as unknown as Record<string, TileRecipe>

function toDef(raw: RawBlock, id: number): BlockDef {
  const textures = typeof raw.textures === 'string'
    ? { top: raw.textures, side: raw.textures, bottom: raw.textures }
    : raw.textures
  return {
    id, name: raw.name, color: [raw.color[0], raw.color[1], raw.color[2]], layer: raw.layer,
    solid: raw.solid, textures, glow: Boolean(raw.glow), fluid: Boolean(raw.fluid),
  }
}

const rawBlocks = registry.blocks as unknown as RawBlock[]
if (rawBlocks.length >= MISSING_ID) throw new Error('Block registry is full; ids must stay below 255')

export const BLOCKS: BlockDef[] = rawBlocks.map(toDef)
export const MISSING: BlockDef = {
  id: MISSING_ID, name: 'missing', color: [255, 0, 255], layer: 'opaque', solid: true,
  textures: { top: 'missing', side: 'missing', bottom: 'missing' }, glow: false, fluid: false,
}

const ids = new Map(BLOCKS.map((block) => [block.name, block.id]))
const warned = new Set<string>()

export function blockId(name: string): number {
  const id = ids.get(name)
  if (id !== undefined) return id
  if (!warned.has(name)) {
    warned.add(name)
    console.warn(`Unknown block "${name}" is shown with the missing texture`)
  }
  return MISSING_ID
}

export function hasBlock(name: string): boolean {
  return ids.has(name)
}

export function blockDef(id: number): BlockDef {
  return BLOCKS[id] ?? MISSING
}

export const LAYER_NONE = 0
export const LAYER_OPAQUE = 1
export const LAYER_CUTOUT = 2
export const LAYER_TRANSLUCENT = 3
const LAYER_CODES: Record<Layer, number> = {
  none: LAYER_NONE, opaque: LAYER_OPAQUE, cutout: LAYER_CUTOUT, translucent: LAYER_TRANSLUCENT,
}

// Flat tables so the mesher never looks up objects in its inner loop.
export const LAYER_BY_ID = new Uint8Array(256)
export const GLOW_BY_ID = new Uint8Array(256)
export const FLUID_BY_ID = new Uint8Array(256)
for (let id = 0; id < 256; id++) {
  const def = blockDef(id)
  LAYER_BY_ID[id] = LAYER_CODES[def.layer]
  GLOW_BY_ID[id] = def.glow ? 1 : 0
  FLUID_BY_ID[id] = def.fluid ? 1 : 0
}
