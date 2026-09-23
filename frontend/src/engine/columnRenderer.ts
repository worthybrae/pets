import * as THREE from 'three'
import { animateWater, buildAtlas, type Atlas } from './atlas'
import type { LayerBuffers } from './mesher'
import type { MeshedResponse, WorkerRequest, WorkerResponse } from './workerProtocol'
import { columnKey, type WorldStore } from './worldStore'
import { CHUNK_SIZE } from './worldgen'

export const MAX_IN_FLIGHT = 4
const WATER_FRAME_SECONDS = 0.25
const LAYER_NAMES = ['opaque', 'cutout', 'translucent'] as const
type LayerName = (typeof LAYER_NAMES)[number]

export interface WorldStats {
  columns: number
  pending: number
  lastMeshMs: number
}

interface ColumnEntry {
  cx: number
  cz: number
  version: number
  failures: number
  meshes: THREE.Mesh[]
}

export function createWorldWorker(): Worker {
  return new Worker(new URL('./world.worker.ts', import.meta.url), { type: 'module' })
}

/** A shared uniform: 1 by day, down to 0.35 at night. */
export interface DaylightUniform {
  value: number
}

/**
 * Multiplies a terrain material's color by the daylight uniform. Vertices with the `glow`
 * attribute set to 1 (lanterns, furnaces, lava, later torches and campfires) keep full brightness.
 */
export function applyDaylight(material: THREE.Material, daylight: DaylightUniform): void {
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uDaylight = daylight
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nattribute float glow;\nvarying float vGlow;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvGlow = glow;')
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nuniform float uDaylight;\nvarying float vGlow;')
      .replace('#include <color_fragment>', '#include <color_fragment>\ndiffuseColor.rgb *= mix(uDaylight, 1.0, vGlow);')
  }
  material.customProgramCacheKey = () => 'terrain-daylight'
}

function toGeometry(buffers: LayerBuffers): THREE.BufferGeometry | null {
  if (buffers.indices.length === 0) return null
  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(buffers.positions, 3))
  geometry.setAttribute('uv', new THREE.BufferAttribute(buffers.uvs, 2))
  geometry.setAttribute('color', new THREE.BufferAttribute(buffers.colors, 3))
  geometry.setAttribute('glow', new THREE.BufferAttribute(buffers.glows, 1))
  geometry.setIndex(new THREE.BufferAttribute(buffers.indices, 1))
  geometry.computeBoundingSphere()
  return geometry
}

/** Loads columns around a point, meshes them in a worker and keeps their three.js meshes. */
export class ColumnRenderer {
  lastMeshMs = 0
  private readonly store: WorldStore
  private readonly group: THREE.Group
  private readonly onError: (message: string) => void
  private readonly worker: Worker
  private readonly atlas: Atlas
  private readonly texture: THREE.DataTexture
  private readonly materials: Record<LayerName, THREE.MeshBasicMaterial>
  private readonly daylight: DaylightUniform = { value: 1 }
  private readonly entries = new Map<string, ColumnEntry>()
  private readonly unsubscribe: () => void
  private queue: string[] = []
  private inFlight = 0
  private waterClock = 0
  private waterStep = 0
  // Renderer-wide, not per-entry: a column unloaded and reloaded gets a fresh entry
  // whose version would otherwise restart at 0 and could collide with a pre-unload reply.
  private nextVersion = 0

  constructor(store: WorldStore, group: THREE.Group, onError: (message: string) => void,
    worker: Worker = createWorldWorker()) {
    this.store = store
    this.group = group
    this.onError = onError
    this.worker = worker
    this.atlas = buildAtlas()
    this.texture = new THREE.DataTexture(this.atlas.data, this.atlas.size, this.atlas.size, THREE.RGBAFormat)
    this.texture.magFilter = THREE.NearestFilter
    this.texture.minFilter = THREE.NearestFilter
    this.texture.generateMipmaps = false
    this.texture.colorSpace = THREE.SRGBColorSpace
    this.texture.needsUpdate = true
    this.materials = {
      opaque: new THREE.MeshBasicMaterial({ map: this.texture, vertexColors: true }),
      cutout: new THREE.MeshBasicMaterial({ map: this.texture, vertexColors: true, alphaTest: 0.5, side: THREE.DoubleSide }),
      translucent: new THREE.MeshBasicMaterial({ map: this.texture, vertexColors: true, transparent: true, depthWrite: false }),
    }
    for (const material of Object.values(this.materials)) applyDaylight(material, this.daylight)
    this.worker.onmessage = (event: MessageEvent<WorkerResponse>) => this.receive(event.data)
    this.worker.onerror = (event) => {
      event.preventDefault()
      this.onError('The world renderer stopped. Try again to restart it.')
    }
    this.unsubscribe = store.subscribe((keys) => {
      for (const key of keys) if (this.entries.has(key)) this.enqueue(key)
      this.pump()
    })
  }

  setView(centerX: number, centerZ: number, viewDistance: number): void {
    const cx = Math.floor(centerX / CHUNK_SIZE), cz = Math.floor(centerZ / CHUNK_SIZE)
    for (const [key, entry] of [...this.entries]) {
      if (Math.max(Math.abs(entry.cx - cx), Math.abs(entry.cz - cz)) > viewDistance + 2) this.unload(key, entry)
    }
    for (let dx = -viewDistance; dx <= viewDistance; dx++) {
      for (let dz = -viewDistance; dz <= viewDistance; dz++) {
        const key = columnKey(cx + dx, cz + dz)
        if (this.entries.has(key)) continue
        this.entries.set(key, { cx: cx + dx, cz: cz + dz, version: 0, failures: 0, meshes: [] })
        this.enqueue(key)
      }
    }
    const distance = (key: string) => {
      const entry = this.entries.get(key)
      return entry ? (entry.cx - cx) ** 2 + (entry.cz - cz) ** 2 : Infinity
    }
    this.queue.sort((a, b) => distance(a) - distance(b))
    this.pump()
  }

  /** Terrain brightness: 1 by day, 0.35 at night. Glowing blocks ignore it. */
  setDaylight(value: number): void {
    this.daylight.value = Math.min(1, Math.max(0, value))
  }

  tick(delta: number): void {
    this.waterClock += delta
    if (this.waterClock < WATER_FRAME_SECONDS) return
    this.waterClock %= WATER_FRAME_SECONDS
    this.waterStep += 1
    animateWater(this.atlas, this.waterStep)
    this.texture.needsUpdate = true
  }

  stats(): WorldStats {
    let columns = 0
    for (const entry of this.entries.values()) if (entry.meshes.length) columns += 1
    return { columns, pending: this.queue.length + this.inFlight, lastMeshMs: this.lastMeshMs }
  }

  /** After a lost WebGL context comes back, upload everything again. */
  restoreGpuResources(): void {
    this.texture.needsUpdate = true
    for (const entry of this.entries.values()) {
      for (const mesh of entry.meshes) {
        for (const attribute of Object.values(mesh.geometry.attributes)) attribute.needsUpdate = true
        if (mesh.geometry.index) mesh.geometry.index.needsUpdate = true
      }
    }
  }

  dispose(): void {
    this.unsubscribe()
    this.worker.terminate()
    for (const [key, entry] of [...this.entries]) this.unload(key, entry)
    for (const material of Object.values(this.materials)) material.dispose()
    this.texture.dispose()
  }

  private enqueue(key: string): void {
    if (!this.queue.includes(key)) this.queue.push(key)
  }

  private pump(): void {
    while (this.inFlight < MAX_IN_FLIGHT && this.queue.length) {
      const key = this.queue.shift()!
      const entry = this.entries.get(key)
      if (!entry) continue
      entry.version = ++this.nextVersion
      const request: WorkerRequest = {
        type: 'mesh', key, cx: entry.cx, cz: entry.cz, seed: this.store.seed,
        edits: this.store.editsNear(entry.cx, entry.cz), version: entry.version,
      }
      this.inFlight += 1
      this.worker.postMessage(request, [request.edits.buffer as ArrayBuffer])
    }
  }

  private receive(response: WorkerResponse): void {
    this.inFlight = Math.max(0, this.inFlight - 1)
    const entry = this.entries.get(response.key)
    if (entry && response.version === entry.version) {
      if (response.type === 'meshed') this.install(entry, response)
      else if (entry.failures++ < 1) this.enqueue(response.key)
      else console.error(`Column ${response.key} could not be meshed: ${response.message}`)
    }
    this.pump()
  }

  private install(entry: ColumnEntry, response: MeshedResponse): void {
    this.removeMeshes(entry)
    for (const name of LAYER_NAMES) {
      const geometry = toGeometry(response.mesh[name])
      if (!geometry) continue
      const mesh = new THREE.Mesh(geometry, this.materials[name])
      if (name === 'translucent') mesh.renderOrder = 1
      mesh.matrixAutoUpdate = false
      entry.meshes.push(mesh)
      this.group.add(mesh)
    }
    entry.failures = 0
    this.store.setBaseColumn(entry.cx, entry.cz, response.base)
    this.lastMeshMs = response.ms
  }

  private removeMeshes(entry: ColumnEntry): void {
    for (const mesh of entry.meshes) {
      this.group.remove(mesh)
      mesh.geometry.dispose()
    }
    entry.meshes = []
  }

  private unload(key: string, entry: ColumnEntry): void {
    this.removeMeshes(entry)
    this.entries.delete(key)
    this.queue = this.queue.filter((queued) => queued !== key)
    this.store.dropBaseColumn(entry.cx, entry.cz)
  }
}
