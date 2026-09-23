import type { PlacedBlock } from '../../engine/worldStore'

type Point = { x: number; z: number }
type ProjectKind = 'station' | 'landing_pad' | 'boardwalk' | 'greenhouse' | 'observatory' | 'sculpture' | 'grove' | 'plaza'

export interface WorldPlan {
  kind: ProjectKind
  site: Point
  variant: number
  observation: string
  clearance: number
  base_y?: number
}

export interface BuildProject {
  name: string
  site: Point
  standOff: number
  /** In the order Mimo places them. */
  blocks: PlacedBlock[]
}

export const ORBITAL_STATION = { x: 48, z: 0, radius: 20, centerY: 22 } as const

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

function compileStation(): BuildProject {
  const { radius, centerY } = ORBITAL_STATION
  const dish = { x: -8, y: 6, radius: 6 }
  const blocks: PlacedBlock[] = []
  for (let y = -radius; y <= radius; y++) {
    for (let x = -radius; x <= radius; x++) {
      for (let z = -radius; z <= radius; z++) {
        if (Math.abs(Math.hypot(x, y, z) - radius) > 0.55) continue
        const dishDistance = Math.hypot(x - dish.x, y - dish.y)
        const inDish = z > radius / 2 && dishDistance < dish.radius
        const material = inDish ? (dishDistance < dish.radius / 2 ? 'solar_panel' : 'dark_slate')
          : Math.abs(y) <= 1 ? 'dark_slate' : 'hull_panel'
        blocks.push({ x: ORBITAL_STATION.x + x, y: centerY + y, z: ORBITAL_STATION.z + z, material })
      }
    }
  }
  blocks.sort((a, b) => a.y - b.y || a.z - b.z || a.x - b.x)
  return { name: names.station, site: { x: ORBITAL_STATION.x, z: ORBITAL_STATION.z }, standOff: radius + 5, blocks }
}

const planCache = new Map<string, BuildProject>()

export function compileWorldPlan(plan: WorldPlan): BuildProject {
  const key = `${plan.kind}:${plan.site.x},${plan.site.z}:${plan.variant}:${plan.base_y ?? 0}`
  const cached = planCache.get(key)
  if (cached) return cached
  if (plan.kind === 'station') {
    const station = compileStation()
    planCache.set(key, station)
    return station
  }
  const { site, kind, variant } = plan
  const baseY = plan.base_y ?? 0
  const blocks: PlacedBlock[] = []
  const add = (x: number, y: number, z: number, material: string) =>
    blocks.push({ x: site.x + x, y: baseY + y, z: site.z + z, material })

  if (kind === 'landing_pad') {
    for (let x = -5; x <= 5; x++) for (let z = -5; z <= 5; z++) {
      if (Math.hypot(x, z) <= 5.5) add(x, 0, z, Math.hypot(x, z) > 4 ? 'limestone' : 'dark_slate')
      if (Math.abs(x) <= 1 && Math.abs(z) <= 1 && (x === 0 || z === 0)) add(x, 1, z, 'brass')
    }
    for (const x of [-5, 5]) for (const z of [-5, 5]) {
      for (let y = 1; y <= 5; y++) add(x, y, z, 'polished_stone')
      add(x, 6, z, 'lantern')
    }
  } else if (kind === 'boardwalk') {
    for (let x = -6; x <= 6; x++) for (let z = -1; z <= 1; z++) {
      add(x, 1, z, 'planks')
      if (Math.abs(z) === 1 && x % 3 === 0) for (let y = 2; y <= 3; y++) add(x, y, z, 'limestone')
    }
    for (let x = -6; x <= 6; x++) for (const z of [-1, 1]) add(x, 3, z, 'planks')
  } else if (kind === 'greenhouse') {
    for (let x = -4; x <= 4; x++) for (let z = -3; z <= 3; z++) {
      add(x, 0, z, 'limestone')
      if (Math.abs(x) < 4 && Math.abs(z) < 3 && (x + z + variant) % 4 === 0) {
        add(x, 1, z, 'leaves')
        add(x, 2, z, 'flower_pink')
      }
      const edge = Math.abs(x) === 4 || Math.abs(z) === 3
      if (edge && !(x === 0 && z === 3)) for (let y = 1; y <= 4; y++) add(x, y, z, y === 1 || y === 4 ? 'oak_log' : 'glass')
      add(x, 5, z, 'glass')
    }
  } else if (kind === 'observatory') {
    for (let y = 0; y <= 8; y++) for (let x = -4; x <= 4; x++) for (let z = -4; z <= 4; z++) {
      const radius = Math.hypot(x, z)
      if (y === 0 && radius <= 4.5) add(x, y, z, 'limestone')
      else if (y > 0 && y < 6 && radius > 3.25 && radius <= 4.5 && !(z === 4 && x === 0 && y < 3)) add(x, y, z, y % 3 === 0 ? 'limestone' : 'polished_stone')
      else if (y >= 6 && Math.hypot(x, z, (y - 6) * 1.6) < 4.5 && Math.hypot(x, z, (y - 6) * 1.6) > 3) add(x, y, z, 'glass')
    }
    for (let y = 8; y <= 12; y++) add(0, y, 0, 'dark_slate')
    add(0, 13, 0, 'lantern')
  } else if (kind === 'sculpture') {
    for (let x = -5; x <= 5; x++) for (let z = -5; z <= 5; z++) if (Math.hypot(x, z) <= 5) add(x, 0, z, 'limestone')
    for (let y = 1; y <= 17; y++) {
      const angle = y * 0.58 + variant
      const x = Math.round(Math.cos(angle) * 3)
      const z = Math.round(Math.sin(angle) * 3)
      const material = y % 4 === 0 ? 'sandstone' : 'verdigris'
      for (let dx = -1; dx <= 1; dx++) for (let dz = -1; dz <= 1; dz++) add(x + dx, y, z + dz, material)
    }
  } else if (kind === 'grove') {
    for (let x = -6; x <= 6; x++) for (let z = -6; z <= 6; z++) if (Math.hypot(x, z) <= 6.5) add(x, 0, z, x % 3 === 0 || z % 3 === 0 ? 'limestone' : 'grass')
    for (const [tx, tz] of [[-4, -3], [4, -3], [-4, 3], [4, 3]] as const) {
      for (let y = 1; y <= 5; y++) add(tx, y, tz, 'oak_log')
      for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) for (let y = 5; y <= 7; y++) {
        if (Math.abs(dx) + Math.abs(dz) + Math.abs(y - 6) <= 4) add(tx + dx, y, tz + dz, 'leaves')
      }
    }
    for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) add(x, 1, z, 'planks')
  } else {
    for (let x = -6; x <= 6; x++) for (let z = -6; z <= 6; z++) if (Math.hypot(x, z) <= 6.5) add(x, 0, z, Math.hypot(x, z) > 4.5 ? 'limestone' : 'polished_stone')
    for (let x = -2; x <= 2; x++) for (let z = -2; z <= 2; z++) if (Math.hypot(x, z) <= 2.5) add(x, 1, z, 'water')
    for (let y = 1; y <= 6; y++) add(0, y, 0, 'limestone')
    add(0, 7, 0, 'lantern')
    for (const x of [-5, 5]) for (const z of [-5, 5]) for (let y = 1; y <= 3; y++) add(x, y, z, 'oak_log')
  }

  const project = { name: names[kind], site, standOff: radii[kind] + 3, blocks }
  planCache.set(key, project)
  if (planCache.size > 256) planCache.delete(planCache.keys().next().value!)
  return project
}

/** Blocks the viewer shows for builds: finished plans in full, the current one up to stepIndex. */
export function overlayBlocks(plans: WorldPlan[], currentIndex: number, stepIndex: number): PlacedBlock[] {
  const blocks: PlacedBlock[] = []
  for (let index = 0; index <= currentIndex && index < plans.length; index++) {
    const project = compileWorldPlan(plans[index])
    const count = index < currentIndex ? project.blocks.length : Math.min(stepIndex, project.blocks.length)
    for (let i = 0; i < count; i++) blocks.push(project.blocks[i])
  }
  return blocks
}
