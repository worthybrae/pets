import { AIR, blockDef, blockId } from './blocks'
import { blockAt, CHUNK_SIZE, columnIndex, DEFAULT_WORLD_SEED, WORLD_MAX_Y, WORLD_MIN_Y } from './worldgen'

export interface PlacedBlock {
  x: number
  y: number
  z: number
  material: string
}

export type DirtyListener = (columns: string[]) => void
type CellMap = Map<string, Map<string, number>>

export function columnKey(cx: number, cz: number): string {
  return `${cx},${cz}`
}

function cellKey(x: number, y: number, z: number): string {
  return `${x},${y},${z}`
}

function chunkOf(value: number): number {
  return Math.floor(value / CHUNK_SIZE)
}

/** Columns whose mesh can change when a block at (x, z) changes: its own plus neighbors on borders. */
export function columnsTouching(x: number, z: number): string[] {
  const cx = chunkOf(x), cz = chunkOf(z)
  const lx = x - cx * CHUNK_SIZE, lz = z - cz * CHUNK_SIZE
  const xs = [cx, ...(lx === 0 ? [cx - 1] : lx === CHUNK_SIZE - 1 ? [cx + 1] : [])]
  const zs = [cz, ...(lz === 0 ? [cz - 1] : lz === CHUNK_SIZE - 1 ? [cz + 1] : [])]
  return xs.flatMap((a) => zs.map((b) => columnKey(a, b)))
}

function put(target: CellMap, x: number, y: number, z: number, id: number): void {
  const column = columnKey(chunkOf(x), chunkOf(z))
  let cells = target.get(column)
  if (!cells) {
    cells = new Map()
    target.set(column, cells)
  }
  cells.set(cellKey(x, y, z), id)
}

function markCell(dirty: Set<string>, cell: string): void {
  const [x, , z] = cell.split(',').map(Number)
  for (const key of columnsTouching(x, z)) dirty.add(key)
}

/**
 * Every block the viewer knows about. Precedence per cell: server edit, then build
 * overlay, then the generated column, then worldgen.
 */
export class WorldStore {
  readonly seed: string
  private readonly base = new Map<string, Uint8Array>()
  private readonly server: CellMap = new Map()
  private overlay: CellMap = new Map()
  private overlayCells = new Map<string, number>()
  private readonly listeners = new Set<DirtyListener>()

  constructor(seed = DEFAULT_WORLD_SEED) {
    this.seed = seed
  }

  getBlock(x: number, y: number, z: number): number {
    if (y < WORLD_MIN_Y || y > WORLD_MAX_Y) return AIR
    const cx = chunkOf(x), cz = chunkOf(z)
    const column = columnKey(cx, cz)
    const cell = cellKey(x, y, z)
    const edited = this.server.get(column)?.get(cell) ?? this.overlay.get(column)?.get(cell)
    if (edited !== undefined) return edited
    const base = this.base.get(column)
    if (base) return base[columnIndex(x - cx * CHUNK_SIZE, y, z - cz * CHUNK_SIZE)]
    return blockId(blockAt(x, y, z, this.seed))
  }

  setBaseColumn(cx: number, cz: number, data: Uint8Array): void {
    this.base.set(columnKey(cx, cz), data)
  }

  dropBaseColumn(cx: number, cz: number): void {
    this.base.delete(columnKey(cx, cz))
  }

  applyServerChanges(changes: PlacedBlock[], reset = false): string[] {
    const dirty = new Set<string>()
    if (reset) {
      for (const cells of this.server.values()) for (const cell of cells.keys()) markCell(dirty, cell)
      this.server.clear()
    }
    for (const { x, y, z, material } of changes) {
      put(this.server, x, y, z, blockId(material))
      for (const key of columnsTouching(x, z)) dirty.add(key)
    }
    return this.emit(dirty)
  }

  /** Replace the client-only build overlay and report the columns that changed. */
  setOverlay(blocks: PlacedBlock[]): string[] {
    const next = new Map<string, number>()
    for (const { x, y, z, material } of blocks) next.set(cellKey(x, y, z), blockId(material))
    const dirty = new Set<string>()
    for (const [cell, id] of next) if (this.overlayCells.get(cell) !== id) markCell(dirty, cell)
    for (const cell of this.overlayCells.keys()) if (!next.has(cell)) markCell(dirty, cell)
    if (dirty.size === 0) return []
    this.overlayCells = next
    this.overlay = new Map()
    for (const [cell, id] of next) {
      const [x, y, z] = cell.split(',').map(Number)
      put(this.overlay, x, y, z, id)
    }
    return this.emit(dirty)
  }

  /** Edits inside a column and its one-cell border as x, y, z, id quadruples. Server edits win. */
  editsNear(cx: number, cz: number): Int32Array {
    const minX = cx * CHUNK_SIZE - 1, maxX = cx * CHUNK_SIZE + CHUNK_SIZE
    const minZ = cz * CHUNK_SIZE - 1, maxZ = cz * CHUNK_SIZE + CHUNK_SIZE
    const merged = new Map<string, number[]>()
    for (const source of [this.overlay, this.server]) {
      for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) {
        const cells = source.get(columnKey(cx + dx, cz + dz))
        if (!cells) continue
        for (const [cell, id] of cells) {
          const [x, y, z] = cell.split(',').map(Number)
          if (x >= minX && x <= maxX && z >= minZ && z <= maxZ) merged.set(cell, [x, y, z, id])
        }
      }
    }
    return Int32Array.from([...merged.values()].flat())
  }

  /** Names of server-placed blocks within `radius` of (x, z), for workstation checks. */
  materialsNear(x: number, z: number, radius: number): Set<string> {
    const found = new Set<string>()
    for (const cells of this.server.values()) {
      for (const [cell, id] of cells) {
        const [bx, , bz] = cell.split(',').map(Number)
        if (id !== AIR && Math.hypot(bx - x, bz - z) <= radius) found.add(blockDef(id).name)
      }
    }
    return found
  }

  subscribe(listener: DirtyListener): () => void {
    this.listeners.add(listener)
    return () => { this.listeners.delete(listener) }
  }

  private emit(dirty: Set<string>): string[] {
    const keys = [...dirty]
    if (keys.length) for (const listener of this.listeners) listener(keys)
    return keys
  }
}
