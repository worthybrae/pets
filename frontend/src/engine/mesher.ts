import { tileUv } from './atlas'
import {
  AIR, CUBE_BY_ID, FLUID_BY_ID, GLOW_BY_ID, LAYER_BY_ID, LAYER_CUTOUT, LAYER_OPAQUE, LAYER_TRANSLUCENT,
} from './blocks'
import { CHUNK_SIZE, WORLD_HEIGHT, WORLD_MIN_Y } from './worldgen'

/** A column plus a one-cell border on each side, so faces and AO at the edges are right. */
export const PADDED = CHUNK_SIZE + 2

/** px and pz run 0..17 (0 and 17 are neighbor cells); layer is worldY - WORLD_MIN_Y. */
export function paddedIndex(px: number, layer: number, pz: number): number {
  return (layer * PADDED + pz) * PADDED + px
}

export interface LayerBuffers {
  positions: Float32Array
  uvs: Float32Array
  colors: Float32Array
  /** 1 for vertices of glowing blocks, which daylight must not darken; else 0. One per vertex. */
  glows: Float32Array
  indices: Uint32Array
}

export interface ColumnMesh {
  opaque: LayerBuffers
  cutout: LayerBuffers
  translucent: LayerBuffers
}

export interface MeshInput {
  cx: number
  cz: number
  volume: Uint8Array
  faceTiles: Uint16Array
}

type Vec3 = [number, number, number]

interface Face {
  dir: Vec3
  /** Bottom-left, bottom-right, top-right, top-left as seen from outside (counter-clockwise). */
  corners: Vec3[]
  shade: number
  /** The two axes (0 = x, 1 = y, 2 = z) that span the face. */
  axes: [number, number]
}

// Same order as the atlas faces: east, west, up, down, south, north.
const FACES: Face[] = [
  { dir: [1, 0, 0], corners: [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]], shade: 0.82, axes: [1, 2] },
  { dir: [-1, 0, 0], corners: [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]], shade: 0.82, axes: [1, 2] },
  { dir: [0, 1, 0], corners: [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]], shade: 1, axes: [0, 2] },
  { dir: [0, -1, 0], corners: [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]], shade: 0.5, axes: [0, 2] },
  { dir: [0, 0, 1], corners: [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], shade: 0.66, axes: [0, 1] },
  { dir: [0, 0, -1], corners: [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]], shade: 0.66, axes: [0, 1] },
]
const CORNER_UV = [[0, 0], [1, 0], [1, 1], [0, 1]]
const AO_LIGHT = [0.45, 0.62, 0.8, 1]
const WATER_DROP = 0.125
const SIDE_FACE = 4
const CROSS: Vec3[][] = [
  [[0.05, 0, 0.05], [0.95, 0, 0.95], [0.95, 1, 0.95], [0.05, 1, 0.05]],
  [[0.95, 0, 0.05], [0.05, 0, 0.95], [0.05, 1, 0.95], [0.95, 1, 0.05]],
]

/** Light level 0 (darkest) to 3 from the two side neighbors and the diagonal neighbor of a corner. */
export function cornerAo(side1: number, side2: number, corner: number): number {
  return side1 && side2 ? 0 : 3 - (side1 + side2 + corner)
}

/** Vertex colors are multiplied in linear space; convert so shading matches the sRGB mockup. */
export function srgbToLinear(value: number): number {
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
}

/** ±3% brightness per block so flat areas don't look printed. */
function tint(x: number, y: number, z: number): number {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(z, 1274126177)
  h = Math.imul(h ^ (h >>> 13), 1103515245)
  return 1 + (((h >>> 16) & 255) / 255 - 0.5) * 0.06
}

class LayerBuilder {
  positions: number[] = []
  uvs: number[] = []
  colors: number[] = []
  glows: number[] = []
  indices: number[] = []

  quad(corners: Vec3[], uv: [number, number, number, number], light: number[], flip: boolean, glow = 0): void {
    const base = this.positions.length / 3
    corners.forEach(([x, y, z], k) => {
      this.positions.push(x, y, z)
      this.uvs.push(CORNER_UV[k][0] ? uv[2] : uv[0], CORNER_UV[k][1] ? uv[3] : uv[1])
      const value = srgbToLinear(Math.min(1, light[k]))
      this.colors.push(value, value, value)
      this.glows.push(glow)
    })
    if (flip) this.indices.push(base + 1, base + 2, base + 3, base + 1, base + 3, base)
    else this.indices.push(base, base + 1, base + 2, base, base + 2, base + 3)
  }

  build(): LayerBuffers {
    return {
      positions: new Float32Array(this.positions),
      uvs: new Float32Array(this.uvs),
      colors: new Float32Array(this.colors),
      glows: new Float32Array(this.glows),
      indices: new Uint32Array(this.indices),
    }
  }
}

export function meshColumn({ cx, cz, volume, faceTiles }: MeshInput): ColumnMesh {
  const opaque = new LayerBuilder()
  const cutout = new LayerBuilder()
  const translucent = new LayerBuilder()
  // -1 means below the world: treated as solid so the underside is never drawn.
  const idAt = (px: number, layer: number, pz: number) =>
    layer < 0 ? -1 : layer >= WORLD_HEIGHT ? AIR : volume[paddedIndex(px, layer, pz)]
  const opaqueAt = (px: number, layer: number, pz: number) => {
    const id = idAt(px, layer, pz)
    return id === -1 || LAYER_BY_ID[id] === LAYER_OPAQUE ? 1 : 0
  }
  const x0 = cx * CHUNK_SIZE - 1, z0 = cz * CHUNK_SIZE - 1

  for (let layer = 0; layer < WORLD_HEIGHT; layer++) {
    for (let pz = 1; pz <= CHUNK_SIZE; pz++) {
      for (let px = 1; px <= CHUNK_SIZE; px++) {
        const id = volume[paddedIndex(px, layer, pz)]
        if (id === AIR) continue
        const kind = LAYER_BY_ID[id]
        if (kind === 0) continue
        const wx = x0 + px, wy = WORLD_MIN_Y + layer, wz = z0 + pz
        const blockTint = tint(wx, wy, wz)
        const glow = GLOW_BY_ID[id] === 1

        if (kind === LAYER_CUTOUT && CUBE_BY_ID[id] === 1) {
          // L3: cactus, ladders and fences are see-through cubes: every face but those against an
          // opaque block or one of their own, face-shaded, with no corner shadows.
          FACES.forEach((face, faceIndex) => {
            const neighbor = idAt(px + face.dir[0], layer + face.dir[1], pz + face.dir[2])
            if (neighbor === -1 || neighbor === id || LAYER_BY_ID[neighbor] === LAYER_OPAQUE) return
            const light = face.shade * blockTint
            cutout.quad(face.corners.map(([x, y, z]) => [wx + x, wy + y, wz + z] as Vec3),
              tileUv(faceTiles[id * 6 + faceIndex]), [light, light, light, light], false, glow ? 1 : 0)
          })
          continue
        }

        if (kind === LAYER_CUTOUT) {
          const uv = tileUv(faceTiles[id * 6 + SIDE_FACE])
          for (const quad of CROSS) {
            cutout.quad(quad.map(([x, y, z]) => [wx + x, wy + y, wz + z] as Vec3), uv,
              [blockTint, blockTint, blockTint, blockTint], false, glow ? 1 : 0)
          }
          continue
        }

        const builder = kind === LAYER_OPAQUE ? opaque : translucent
        const above = idAt(px, layer + 1, pz)
        const lowered = FLUID_BY_ID[id] === 1 && above !== id && LAYER_BY_ID[above] !== LAYER_OPAQUE
        FACES.forEach((face, faceIndex) => {
          const [dx, dy, dz] = face.dir
          const nx = px + dx, nl = layer + dy, nz = pz + dz
          const neighbor = idAt(nx, nl, nz)
          if (neighbor === -1 || LAYER_BY_ID[neighbor] === LAYER_OPAQUE) return
          if (kind === LAYER_TRANSLUCENT && neighbor === id) return
          const aos: number[] = []
          const corners = face.corners.map((corner): Vec3 => {
            let ao = 3
            if (!glow) {
              const [u, v] = face.axes
              const a: Vec3 = [0, 0, 0], b: Vec3 = [0, 0, 0]
              a[u] = corner[u] ? 1 : -1
              b[v] = corner[v] ? 1 : -1
              ao = cornerAo(
                opaqueAt(nx + a[0], nl + a[1], nz + a[2]),
                opaqueAt(nx + b[0], nl + b[1], nz + b[2]),
                opaqueAt(nx + a[0] + b[0], nl + a[1] + b[1], nz + a[2] + b[2]),
              )
            }
            aos.push(ao)
            return [wx + corner[0], wy + (lowered && corner[1] === 1 ? 1 - WATER_DROP : corner[1]), wz + corner[2]]
          })
          const light = aos.map((ao) => face.shade * AO_LIGHT[ao] * blockTint)
          // Split along the diagonal that holds the odd corner so gradients don't crease.
          const flip = aos[0] + aos[2] > aos[1] + aos[3]
          builder.quad(corners, tileUv(faceTiles[id * 6 + faceIndex]), light, flip, glow ? 1 : 0)
        })
      }
    }
  }
  return { opaque: opaque.build(), cutout: cutout.build(), translucent: translucent.build() }
}
