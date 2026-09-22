import type { Chunk, Voxel } from '../../types/world'
import {
  ensureTerrainAround, makeProject, ORBITAL_STATION, placeVoxels, worldForProgress,
  type BuildProject,
} from './expandingWorld'

type Point = { x: number; z: number }
type Color = readonly [number, number, number]
type ProjectKind = 'station' | 'landing_pad' | 'boardwalk' | 'greenhouse' | 'observatory' | 'sculpture' | 'grove' | 'plaza'

export interface WorldPlan {
  kind: ProjectKind
  site: Point
  variant: number
  observation: string
  clearance: number
}

export interface PlannerState {
  plans: WorldPlan[]
  currentIndex: number
  stepIndex: number
}

const names: Record<ProjectKind, string> = {
  station: 'an orbital station', landing_pad: 'a station landing pad',
  boardwalk: 'a boardwalk over the pond', greenhouse: 'a glass greenhouse',
  observatory: 'a hilltop observatory', sculpture: 'a tall voxel sculpture',
  grove: 'a sheltered grove', plaza: 'a fountain plaza',
}
const radii: Record<ProjectKind, number> = {
  station: ORBITAL_STATION.radius, landing_pad: 6, boardwalk: 6,
  greenhouse: 5, observatory: 5, sculpture: 5, grove: 7, plaza: 7,
}

function block(x: number, y: number, z: number, color: Color, material?: Voxel['material']): Voxel {
  return { x, y, z, r: color[0], g: color[1], b: color[2], a: 255, material }
}

export function compileWorldPlan(plan: WorldPlan): BuildProject {
  if (plan.kind === 'station') return makeProject(0)
  const { site, kind, variant } = plan
  const voxels: Voxel[] = []
  const add = (x: number, y: number, z: number, color: Color, material?: Voxel['material']) =>
    voxels.push(block(site.x + x, y, site.z + z, color, material))
  const pale: Color = [227, 211, 181]
  const stone: Color = [169, 183, 178]
  const dark: Color = [82, 104, 111]
  const wood: Color = [139, 105, 82]
  const leaf: Color = variant % 2 ? [91, 159, 127] : [113, 174, 139]

  if (kind === 'landing_pad') {
    for (let x = -5; x <= 5; x++) for (let z = -5; z <= 5; z++) {
      if (Math.hypot(x, z) <= 5.5) add(x, 0, z, Math.hypot(x, z) > 4 ? pale : dark)
      if (Math.abs(x) <= 1 && Math.abs(z) <= 1 && (x === 0 || z === 0)) add(x, 1, z, [226, 192, 126])
    }
    for (const x of [-5, 5]) for (const z of [-5, 5]) {
      for (let y = 1; y <= 5; y++) add(x, y, z, stone)
      add(x, 6, z, [245, 207, 139], 'lantern')
    }
  } else if (kind === 'boardwalk') {
    for (let x = -6; x <= 6; x++) for (let z = -1; z <= 1; z++) {
      add(x, 1, z, wood, 'wood')
      if (Math.abs(z) === 1 && x % 3 === 0) for (let y = 2; y <= 3; y++) add(x, y, z, pale)
    }
    for (let x = -6; x <= 6; x++) for (const z of [-1, 1]) add(x, 3, z, [202, 178, 142], 'wood')
  } else if (kind === 'greenhouse') {
    for (let x = -4; x <= 4; x++) for (let z = -3; z <= 3; z++) {
      add(x, 0, z, pale)
      if (Math.abs(x) < 4 && Math.abs(z) < 3 && (x + z + variant) % 4 === 0) {
        add(x, 1, z, leaf)
        add(x, 2, z, [242, 186, 160])
      }
      const edge = Math.abs(x) === 4 || Math.abs(z) === 3
      if (edge && !(x === 0 && z === 3)) for (let y = 1; y <= 4; y++) add(x, y, z, y === 1 || y === 4 ? wood : [145, 207, 199], y === 1 || y === 4 ? 'wood' : 'glass')
      add(x, 5, z, [175, 220, 213], 'glass')
    }
  } else if (kind === 'observatory') {
    for (let y = 0; y <= 8; y++) for (let x = -4; x <= 4; x++) for (let z = -4; z <= 4; z++) {
      const radius = Math.hypot(x, z)
      if (y === 0 && radius <= 4.5) add(x, y, z, pale)
      else if (y > 0 && y < 6 && radius > 3.25 && radius <= 4.5 && !(z === 4 && x === 0 && y < 3)) add(x, y, z, y % 3 === 0 ? pale : stone)
      else if (y >= 6 && Math.hypot(x, z, (y - 6) * 1.6) < 4.5 && Math.hypot(x, z, (y - 6) * 1.6) > 3) add(x, y, z, [116, 159, 177], 'glass')
    }
    for (let y = 8; y <= 12; y++) add(0, y, 0, dark)
    add(0, 13, 0, [240, 204, 139], 'lantern')
  } else if (kind === 'sculpture') {
    for (let x = -5; x <= 5; x++) for (let z = -5; z <= 5; z++) if (Math.hypot(x, z) <= 5) add(x, 0, z, pale)
    for (let y = 1; y <= 17; y++) {
      const angle = y * 0.58 + variant
      const x = Math.round(Math.cos(angle) * 3)
      const z = Math.round(Math.sin(angle) * 3)
      const color: Color = y % 4 === 0 ? [245, 197, 151] : [152, 192, 187]
      for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) add(x + dx, y, z + dz, color)
    }
  } else if (kind === 'grove') {
    for (let x = -6; x <= 6; x++) for (let z = -6; z <= 6; z++) if (Math.hypot(x, z) <= 6.5) add(x, 0, z, x % 3 === 0 || z % 3 === 0 ? pale : [128, 176, 136])
    for (const [tx, tz] of [[-4, -3], [4, -3], [-4, 3], [4, 3]] as const) {
      for (let y = 1; y <= 5; y++) add(tx, y, tz, wood, 'wood')
      for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let y = 5; y <= 7; y++) {
        if (Math.abs(dx) + Math.abs(dz) + Math.abs(y - 6) <= 4) add(tx + dx, y, tz + dz, leaf, 'leaves')
      }
    }
    for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) add(x, 1, z, [202, 180, 143])
  } else {
    for (let x = -6; x <= 6; x++) for (let z = -6; z <= 6; z++) if (Math.hypot(x, z) <= 6.5) add(x, 0, z, Math.hypot(x, z) > 4.5 ? pale : stone)
    for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) if (Math.hypot(x, z) <= 2.5) add(x, 1, z, [114, 182, 201], 'water')
    for (let y = 1; y <= 6; y++) add(0, y, 0, pale)
    add(0, 7, 0, [244, 198, 152], 'lantern')
    for (const x of [-5, 5]) for (const z of [-5, 5]) for (let y = 1; y <= 3; y++) add(x, y, z, wood)
  }

  return { name: names[kind], site, standOff: radii[kind] + 3, voxels }
}

export function worldForPlannerState(state: PlannerState, center?: Point, visibleRadius = 96): Chunk[] {
  let chunks = worldForProgress({ projectIndex: 0, stepIndex: 0 })
  for (let index = 0; index <= state.currentIndex; index++) {
    const plan = state.plans[index]
    if (center && Math.hypot(plan.site.x - center.x, plan.site.z - center.z) > visibleRadius + radii[plan.kind]) continue
    const project = compileWorldPlan(plan)
    chunks = ensureTerrainAround(chunks, project.site.x, project.site.z)
    const count = index < state.currentIndex ? project.voxels.length : Math.min(state.stepIndex, project.voxels.length)
    chunks = placeVoxels(chunks, project.voxels.slice(0, count))
  }
  return chunks
}
