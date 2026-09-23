import { PADDED, paddedIndex } from './mesher'
import { CHUNK_SIZE, columnIndex, generateColumn, WORLD_HEIGHT, WORLD_MIN_Y } from './worldgen'

/** Generated columns, least recently used evicted first. */
export class ColumnCache {
  readonly seed: string
  private readonly limit: number
  private readonly columns = new Map<string, Uint8Array>()

  constructor(seed: string, limit = 256) {
    this.seed = seed
    this.limit = limit
  }

  get size(): number {
    return this.columns.size
  }

  get(cx: number, cz: number): Uint8Array {
    const key = `${cx},${cz}`
    const cached = this.columns.get(key)
    if (cached) {
      this.columns.delete(key)
      this.columns.set(key, cached)
      return cached
    }
    const column = generateColumn(cx, cz, this.seed)
    this.columns.set(key, column)
    if (this.columns.size > this.limit) this.columns.delete(this.columns.keys().next().value!)
    return column
  }
}

/** The mesher's input: this column plus a one-cell border, with edits applied on top. */
export function buildPaddedVolume(cx: number, cz: number, columnAt: (cx: number, cz: number) => Uint8Array,
  edits: Int32Array): Uint8Array {
  const volume = new Uint8Array(PADDED * PADDED * WORLD_HEIGHT)
  for (let pz = 0; pz < PADDED; pz++) {
    const wz = cz * CHUNK_SIZE + pz - 1
    const sourceZ = Math.floor(wz / CHUNK_SIZE), lz = wz - sourceZ * CHUNK_SIZE
    for (let px = 0; px < PADDED; px++) {
      const wx = cx * CHUNK_SIZE + px - 1
      const sourceX = Math.floor(wx / CHUNK_SIZE), lx = wx - sourceX * CHUNK_SIZE
      const source = columnAt(sourceX, sourceZ)
      for (let layer = 0; layer < WORLD_HEIGHT; layer++) {
        volume[paddedIndex(px, layer, pz)] = source[columnIndex(lx, WORLD_MIN_Y + layer, lz)]
      }
    }
  }
  for (let i = 0; i < edits.length; i += 4) {
    const px = edits[i] - cx * CHUNK_SIZE + 1
    const layer = edits[i + 1] - WORLD_MIN_Y
    const pz = edits[i + 2] - cz * CHUNK_SIZE + 1
    if (px < 0 || px >= PADDED || pz < 0 || pz >= PADDED || layer < 0 || layer >= WORLD_HEIGHT) continue
    volume[paddedIndex(px, layer, pz)] = edits[i + 3]
  }
  return volume
}
