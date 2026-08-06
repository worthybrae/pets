import { useRef, useMemo, useEffect } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Phase } from './types'

// ── Config ──

const BASE_RADIUS = 12       // voxels across half-width (higher = more detail)
const GAP = 0.06              // gap between voxels (0 = touching, 0.1 = visible seams)
const BEVEL = 0.04            // chamfer size on box edges

// ── Types ──

interface VoxelEggProps {
  color: { base: [number, number, number]; core: [number, number, number] }
  shape: number
  size: number
  scalePattern: number
  phase: Phase
  eggScaleRef: React.MutableRefObject<number>
  onIntroComplete: () => void
  mouseRef: React.MutableRefObject<{ x: number; y: number }>
  onHover?: (hovered: boolean) => void
}

// ── Noise ──

function hash3(x: number, y: number, z: number): number {
  let h = ((x * 73856093) ^ (y * 19349663) ^ (z * 83492791)) | 0
  h = Math.imul((h >> 16) ^ h, 0x45d9f3b)
  h = Math.imul((h >> 16) ^ h, 0x45d9f3b)
  return (Math.abs((h >> 16) ^ h) % 10000) / 10000
}

function smoothNoise(x: number, y: number, z: number, freq: number): number {
  const fx = x * freq, fy = y * freq, fz = z * freq
  const ix = Math.floor(fx), iy = Math.floor(fy), iz = Math.floor(fz)
  const dx = fx - ix, dy = fy - iy, dz = fz - iz
  const sx = dx * dx * (3 - 2 * dx)
  const sy = dy * dy * (3 - 2 * dy)
  const sz = dz * dz * (3 - 2 * dz)
  const c00 = hash3(ix, iy, iz) * (1 - sx) + hash3(ix + 1, iy, iz) * sx
  const c10 = hash3(ix, iy + 1, iz) * (1 - sx) + hash3(ix + 1, iy + 1, iz) * sx
  const c01 = hash3(ix, iy, iz + 1) * (1 - sx) + hash3(ix + 1, iy, iz + 1) * sx
  const c11 = hash3(ix, iy + 1, iz + 1) * (1 - sx) + hash3(ix + 1, iy + 1, iz + 1) * sx
  return (c00 * (1 - sy) + c10 * sy) * (1 - sz) + (c01 * (1 - sy) + c11 * sy) * sz
}

function fbm(x: number, y: number, z: number, octaves: number, freq: number): number {
  let v = 0, a = 1, f = freq, t = 0
  for (let i = 0; i < octaves; i++) { v += smoothNoise(x, y, z, f) * a; t += a; a *= 0.5; f *= 2.1 }
  return v / t
}

function clamp(v: number, lo: number, hi: number) { return v < lo ? lo : v > hi ? hi : v }

function lerpC(a: [number, number, number], b: [number, number, number], t: number): [number, number, number] {
  const tc = clamp(t, 0, 1)
  return [a[0] + (b[0] - a[0]) * tc, a[1] + (b[1] - a[1]) * tc, a[2] + (b[2] - a[2]) * tc]
}

// ── Egg shape ──

interface EggShape { heightScale: number; widthScale: number; topNarrow: number; asymmetry: number; bellyOffset: number }

const SHAPES: Record<number, EggShape> = {
  0: { heightScale: 1.30, widthScale: 1.05, topNarrow: 0.35, asymmetry: 0.10, bellyOffset: -0.05 },
  1: { heightScale: 1.45, widthScale: 0.92, topNarrow: 0.42, asymmetry: 0.06, bellyOffset: -0.10 },
  2: { heightScale: 1.10, widthScale: 1.18, topNarrow: 0.40, asymmetry: 0.20, bellyOffset: -0.08 },
  3: { heightScale: 1.65, widthScale: 0.80, topNarrow: 0.48, asymmetry: 0.04, bellyOffset: -0.12 },
  4: { heightScale: 1.38, widthScale: 1.00, topNarrow: 0.60, asymmetry: 0.28, bellyOffset: -0.25 },
  5: { heightScale: 1.20, widthScale: 1.14, topNarrow: 0.30, asymmetry: 0.22, bellyOffset: -0.18 },
  6: { heightScale: 1.42, widthScale: 0.96, topNarrow: 0.68, asymmetry: 0.35, bellyOffset: -0.30 },
  7: { heightScale: 1.80, widthScale: 0.70, topNarrow: 0.52, asymmetry: 0.02, bellyOffset: -0.08 },
}

function eggMaxR(ny: number, s: EggShape): number {
  const shifted = ny - s.bellyOffset * 0.3
  const t = clamp((shifted + 1) / 2, 0, 1)
  return Math.sin(t * Math.PI) *
    (1 - s.topNarrow * Math.pow(Math.max(0, t - 0.35) / 0.65, 1.8)) *
    (1 + s.asymmetry * Math.pow(Math.max(0, 0.5 - t), 2) * 4) *
    s.widthScale
}

// ── Scale patterns ──

function patternBlend(x: number, y: number, z: number, pattern: number, R: number): number {
  const nx = x / R, ny = y / R, nz = z / R
  const angle = Math.atan2(nz, nx)
  switch (pattern) {
    case 0: return 0
    case 1: { const n = fbm(nx * 6, ny * 6, nz * 6, 3, 1); return n > 0.55 ? (n - 0.55) * 4 : 0 }
    case 2: { const b = Math.sin(ny * 8) * 0.5 + 0.5 + smoothNoise(nx * 2, ny * 2, nz * 2, 1.5) * 0.15; return Math.pow(clamp(b, 0, 1), 3) > 0.4 ? 0.65 : 0 }
    case 3: { const v = Math.min(Math.abs(Math.sin(nx * 4 + nz * 7 + ny * 2.5)), Math.abs(Math.sin(ny * 5 - nx * 6 + nz * 3))); return v < 0.1 ? (1 - v / 0.1) * 0.9 : 0 }
    case 4: { const e = Math.min(Math.abs(((nx * 4 + ny * 2) % 1) - 0.5) * 2, Math.abs(((ny * 4 + nz * 2) % 1) - 0.5) * 2); return e < 0.15 ? 0.85 : e < 0.3 ? 0.2 : 0 }
    case 5: { const s = Math.sin(angle * 3.5 + ny * 12) * 0.5 + 0.5 + smoothNoise(nx * 3, ny * 3, nz * 3, 1) * 0.15; return clamp(s, 0, 1) > 0.7 ? 0.75 : 0 }
    case 6: { const r = Math.abs(Math.sin(angle * 6 + ny * 10) * Math.cos(ny * 15 - angle * 3) + smoothNoise(nx * 4, ny * 4, nz * 4, 2) * 0.5); return r > 0.6 ? 0.9 : 0 }
    case 7: { const c = Math.sqrt(smoothNoise(nx * 3, ny * 3, nz * 3, 1) ** 2 + smoothNoise(nx * 3 + 50, ny * 3 + 50, nz * 3 + 50, 1) ** 2); return Math.max(Math.abs(c - 0.5) < 0.06 ? 0.8 : 0, smoothNoise(nx * 8, ny * 8, nz * 8, 2) * 0.35) }
    default: return 0
  }
}

// ── Baked AO: count how many of the 8 corner-sharing voxels are solid ──

function computeAO(x: number, y: number, z: number, occupied: Set<string>): number {
  // Check all 26 neighbors (6 face + 12 edge + 8 corner)
  // Weight face neighbors more heavily
  let occlusion = 0
  const k = (a: number, b: number, c: number) => `${a},${b},${c}`
  // Face neighbors (weight 0.25 each, 6 total)
  const faces: [number, number, number][] = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]
  for (const [dx, dy, dz] of faces) {
    if (occupied.has(k(x + dx, y + dy, z + dz))) occlusion += 0.15
  }
  // Edge neighbors (weight 0.1 each)
  const edges: [number, number, number][] = [
    [1,1,0],[1,-1,0],[-1,1,0],[-1,-1,0],
    [1,0,1],[1,0,-1],[-1,0,1],[-1,0,-1],
    [0,1,1],[0,1,-1],[0,-1,1],[0,-1,-1],
  ]
  for (const [dx, dy, dz] of edges) {
    if (occupied.has(k(x + dx, y + dy, z + dz))) occlusion += 0.06
  }
  // Corner neighbors (weight 0.05 each)
  const corners: [number, number, number][] = [
    [1,1,1],[1,1,-1],[1,-1,1],[1,-1,-1],
    [-1,1,1],[-1,1,-1],[-1,-1,1],[-1,-1,-1],
  ]
  for (const [dx, dy, dz] of corners) {
    if (occupied.has(k(x + dx, y + dy, z + dz))) occlusion += 0.04
  }
  return clamp(occlusion, 0, 1)
}

// ── Chamfered box geometry ──

function createChamferedBox(size: number, bevel: number): THREE.BufferGeometry {
  const s = size / 2
  const b = bevel
  const inner = s - b

  // Use a rounded box approach: scale a sphere into a box shape
  // Simpler: use a regular box and add beveled edges via extra vertices
  // Simplest that works: use THREE.BoxGeometry with a tiny bevel via normal averaging
  // Actually, the best simple approach for instanced mesh: use a slightly smaller box
  // with a second inverted-normal shell for edge highlight

  // For real bevels, use a custom geometry with chamfered edges
  const geo = new THREE.BoxGeometry(size, size, size, 1, 1, 1)

  // Adjust corner vertices inward to create chamfers
  const pos = geo.attributes.position
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i)
    // Count how many axes are at max extent
    const atEdge = [Math.abs(Math.abs(x) - s) < 0.001, Math.abs(Math.abs(y) - s) < 0.001, Math.abs(Math.abs(z) - s) < 0.001]
    const edgeCount = atEdge.filter(Boolean).length

    if (edgeCount >= 2) {
      // Corner or edge vertex — pull inward slightly
      const factor = edgeCount === 3 ? 0.7 : 0.85
      pos.setX(i, x * factor + Math.sign(x) * s * (1 - factor))
      pos.setY(i, y * factor + Math.sign(y) * s * (1 - factor))
      pos.setZ(i, z * factor + Math.sign(z) * s * (1 - factor))
    }
  }

  geo.computeVertexNormals()
  return geo
}

// ── Main generator ──

function generateEggVoxels(
  shapeIdx: number,
  size: number,
  scalePattern: number,
  baseColor: [number, number, number],
  coreColor: [number, number, number],
): { x: number; y: number; z: number; r: number; g: number; b: number }[] {
  const shape = SHAPES[shapeIdx] || SHAPES[0]
  const R = Math.round(BASE_RADIUS * size)
  const H = Math.round(R * shape.heightScale)
  const W = Math.round(R * shape.widthScale) + 2

  // ── 1. Build occupancy ──
  const key = (x: number, y: number, z: number) => `${x},${y},${z}`
  const occupied = new Set<string>()

  for (let y = -H - 1; y <= H + 1; y++) {
    const maxR = eggMaxR(y / H, shape) * R
    if (maxR < 0.3) continue
    for (let x = -W; x <= W; x++) {
      for (let z = -W; z <= W; z++) {
        if (Math.sqrt(x * x + z * z) <= maxR) occupied.add(key(x, y, z))
      }
    }
  }

  // ── 2. Extract surface + compute colors ──
  const DIRS: [number, number, number][] = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0,0,1],[0,0,-1]]
  const voxels: { x: number; y: number; z: number; r: number; g: number; b: number }[] = []

  // Color palette
  const shadowCol: [number, number, number] = [baseColor[0] * 0.3, baseColor[1] * 0.3, baseColor[2] * 0.32]
  const litCol: [number, number, number] = [
    Math.min(255, baseColor[0] * 1.2 + 20),
    Math.min(255, baseColor[1] * 1.2 + 18),
    Math.min(255, baseColor[2] * 1.2 + 15),
  ]
  const brightCol: [number, number, number] = [
    Math.min(255, baseColor[0] * 1.35 + 45),
    Math.min(255, baseColor[1] * 1.35 + 40),
    Math.min(255, baseColor[2] * 1.35 + 35),
  ]
  const coreAccent: [number, number, number] = [
    Math.min(255, coreColor[0] * 1.1 + 10),
    Math.min(255, coreColor[1] * 1.1 + 10),
    Math.min(255, coreColor[2] * 1.1 + 10),
  ]

  // Light setup
  const keyLt = { x: 0.35, y: 0.75, z: 0.45 }
  const fillLt = { x: -0.5, y: 0.2, z: -0.3 }

  for (const k2 of occupied) {
    const [x, y, z] = k2.split(',').map(Number)

    // Surface test
    let isSurface = false
    for (const [dx, dy, dz] of DIRS) {
      if (!occupied.has(key(x + dx, y + dy, z + dz))) { isSurface = true; break }
    }
    if (!isSurface) continue

    // ── Normal (gradient of egg SDF) ──
    const len = Math.sqrt(x * x + y * y * 0.5 + z * z) || 1
    let nrmX = x / len, nrmY = y * 0.6 / len, nrmZ = z / len
    const nrmLen = Math.sqrt(nrmX * nrmX + nrmY * nrmY + nrmZ * nrmZ) || 1
    nrmX /= nrmLen; nrmY /= nrmLen; nrmZ /= nrmLen

    // ── Lighting ──
    const keyDot = clamp(nrmX * keyLt.x + nrmY * keyLt.y + nrmZ * keyLt.z, 0, 1)
    const fillDot = clamp(nrmX * fillLt.x + nrmY * fillLt.y + nrmZ * fillLt.z, 0, 1)
    const viewDot = Math.abs(nrmZ)
    const fresnel = Math.pow(1 - viewDot, 3.5) * 0.4

    const keyWrap = keyDot * 0.65 + 0.35
    const fillWrap = fillDot * 0.3 + 0.05
    const totalLight = clamp(keyWrap * 0.55 + fillWrap * 0.2 + 0.25, 0, 1)

    // ── AO ──
    const ao = computeAO(x, y, z, occupied)
    const aoFactor = 1.0 - ao * 0.55 // darken occluded voxels

    // ── Base color from light ramp ──
    let col: [number, number, number]
    if (totalLight < 0.45) {
      col = lerpC(shadowCol, baseColor, totalLight / 0.45)
    } else if (totalLight < 0.75) {
      col = lerpC(baseColor, litCol, (totalLight - 0.45) / 0.3)
    } else {
      col = lerpC(litCol, brightCol, (totalLight - 0.75) / 0.25)
    }

    // Apply AO
    col = [col[0] * aoFactor, col[1] * aoFactor, col[2] * aoFactor]

    // ── Height tint ──
    const heightT = (y / H + 1) / 2
    col[0] += heightT * 10 - 3
    col[1] += heightT * 5 - 1
    col[2] -= heightT * 4 - 2

    // ── Rim/fresnel → core color glow at edges ──
    col = lerpC(col, coreAccent, fresnel)

    // ── Scale pattern ──
    const pBlend = patternBlend(x, y, z, scalePattern, R)
    if (pBlend > 0) col = lerpC(col, coreAccent, pBlend * 0.6)

    // ── Organic noise ──
    const noise = fbm(x + 0.5, y + 0.5, z + 0.5, 2, 0.12) - 0.5
    col[0] += noise * 18
    col[1] += noise * 14
    col[2] += noise * 20

    // ── Specular hint ──
    col[0] += Math.pow(keyDot, 10) * 40
    col[1] += Math.pow(keyDot, 10) * 38
    col[2] += Math.pow(keyDot, 10) * 35

    voxels.push({
      x, y, z,
      r: clamp(Math.round(col[0]), 0, 255),
      g: clamp(Math.round(col[1]), 0, 255),
      b: clamp(Math.round(col[2]), 0, 255),
    })
  }

  return voxels
}

export { generateEggVoxels }

// ── Component ──

export default function VoxelEgg({
  color, shape, size, scalePattern, phase,
  eggScaleRef, onIntroComplete, mouseRef, onHover,
}: VoxelEggProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const groupRef = useRef<THREE.Group>(null)
  const timeRef = useRef(0)
  const growthRef = useRef(0)
  const shakeRef = useRef(0)
  const dissolveRef = useRef(0)

  const voxels = useMemo(
    () => generateEggVoxels(shape, size, scalePattern, color.base, color.core),
    [shape, size, scalePattern, color.base, color.core],
  )

  const dissolveOrder = useMemo(() => {
    if (!voxels.length) return new Float32Array(0)
    let minY = Infinity, maxY = -Infinity
    for (const v of voxels) { if (v.y < minY) minY = v.y; if (v.y > maxY) maxY = v.y }
    const range = maxY - minY || 1
    const arr = new Float32Array(voxels.length)
    for (let i = 0; i < voxels.length; i++) {
      const v = voxels[i]
      arr[i] = ((v.y - minY) / range) * 0.7 + hash3(v.x * 7, v.y * 13, v.z * 19) * 0.3
    }
    return arr
  }, [voxels])

  // Chamfered box geometry
  const boxGeo = useMemo(() => {
    const renderSize = 1 - GAP
    return createChamferedBox(renderSize, BEVEL)
  }, [])

  // Scale: egg should be ~1.2 world units tall
  const baseScale = useMemo(() => 1.2 / (Math.round(BASE_RADIUS * size) * 2 * (SHAPES[shape]?.heightScale || 1.3)), [size, shape])

  useEffect(() => {
    eggScaleRef.current = 1
    onIntroComplete()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useFrame((_, delta) => {
    timeRef.current += delta
    const t = timeRef.current
    if (!meshRef.current || !groupRef.current) return

    // Phase animations
    let targetGrowth = 0
    if (phase === 'hatching' || phase === 'stats') targetGrowth = 1.0
    if (phase === 'generating') targetGrowth = 1.08
    growthRef.current += (targetGrowth - growthRef.current) * 0.04

    if (phase === 'reveal') dissolveRef.current = Math.min(1, dissolveRef.current + delta * 0.6)
    if (phase === 'generating') shakeRef.current = Math.min(1, shakeRef.current + delta * 0.02)
    else if (phase === 'reveal') shakeRef.current = Math.max(0, shakeRef.current - delta * 4)
    else shakeRef.current *= 0.92

    // Group
    const growth = 0.82 + growthRef.current * 0.58
    const scale = baseScale * growth * (1 - dissolveRef.current * 0.15)
    const shake = shakeRef.current

    groupRef.current.rotation.y += delta * 0.08 + mouseRef.current.x * 0.005
    groupRef.current.rotation.x = mouseRef.current.y * 0.05 + shake * Math.sin(t * 28) * 0.035
    groupRef.current.position.x = shake * Math.cos(t * 20) * 0.02
    groupRef.current.scale.setScalar(scale)

    // Voxel instances
    const mesh = meshRef.current
    const matrix = new THREE.Matrix4()
    const col = new THREE.Color()
    const dissolve = dissolveRef.current
    const beat = Math.sin(t * 0.5) * 0.5 + 0.5

    for (let i = 0; i < voxels.length; i++) {
      const v = voxels[i]
      const dOrd = dissolveOrder[i]

      if (dissolve > 0 && dOrd > (1 - dissolve) * 1.15) {
        const scatter = clamp((dissolve - (1 - dOrd / 1.15)) * 2, 0, 1)
        const hx = hash3(v.x * 3, v.y * 5, v.z * 7) - 0.5
        const hy = hash3(v.x * 31, v.y * 37, v.z * 41)
        const hz = hash3(v.x * 11, v.y * 17, v.z * 23) - 0.5
        matrix.identity()
        matrix.setPosition(v.x + hx * scatter * 18, v.y + hy * scatter * 25, v.z + hz * scatter * 18)
        const s = Math.max(0, 1 - scatter * 1.5)
        matrix.scale(new THREE.Vector3(s, s, s))
      } else {
        const breathe = 1 + beat * 0.008 * growthRef.current
        matrix.identity()
        matrix.setPosition(v.x, v.y, v.z)
        matrix.scale(new THREE.Vector3(breathe, breathe, breathe))
      }

      mesh.setMatrixAt(i, matrix)

      let cr = v.r / 255, cg = v.g / 255, cb = v.b / 255
      if (phase === 'generating' && shakeRef.current > 0.1) {
        const warmth = beat * 0.05 * shakeRef.current
        cr = Math.min(1, cr + warmth)
        cg = Math.min(1, cg + warmth * 0.25)
      }
      col.setRGB(cr, cg, cb, THREE.SRGBColorSpace)
      mesh.setColorAt(i, col)
    }

    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  })

  if (!voxels.length || dissolveRef.current >= 0.99) return null

  return (
    <group ref={groupRef}>
      <instancedMesh
        ref={meshRef}
        args={[boxGeo, undefined, voxels.length]}
        frustumCulled={false}
        onPointerOver={() => onHover?.(true)}
        onPointerOut={() => onHover?.(false)}
      >
        <meshPhysicalMaterial
          roughness={0.35}
          metalness={0.08}
          clearcoat={0.8}
          clearcoatRoughness={0.15}
        />
      </instancedMesh>
    </group>
  )
}
