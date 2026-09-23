import * as THREE from 'three'
import { describe, expect, it, vi } from 'vitest'
import { applyDaylight, ColumnRenderer, MAX_IN_FLIGHT } from './columnRenderer'
import type { LayerBuffers } from './mesher'
import type { MeshRequest, WorkerResponse } from './workerProtocol'
import { WorldStore } from './worldStore'

class FakeWorker {
  posted: MeshRequest[] = []
  onmessage: ((event: MessageEvent<WorkerResponse>) => void) | null = null
  onerror: ((event: ErrorEvent) => void) | null = null
  terminated = false
  postMessage(message: MeshRequest) { this.posted.push(message) }
  terminate() { this.terminated = true }
  reply(response: WorkerResponse) { this.onmessage?.({ data: response } as MessageEvent<WorkerResponse>) }
}

const empty = (): LayerBuffers => ({
  positions: new Float32Array(0), uvs: new Float32Array(0), colors: new Float32Array(0), glows: new Float32Array(0),
  indices: new Uint32Array(0),
})
const oneQuad = (): LayerBuffers => ({
  positions: new Float32Array(12), uvs: new Float32Array(8), colors: new Float32Array(12), glows: new Float32Array(4),
  indices: new Uint32Array([0, 1, 2, 0, 2, 3]),
})

/** Run a material's onBeforeCompile on three's own basic shader, as the renderer would. */
function compile(material: THREE.Material) {
  const shader = {
    uniforms: {} as Record<string, THREE.IUniform>,
    vertexShader: THREE.ShaderLib.basic.vertexShader,
    fragmentShader: THREE.ShaderLib.basic.fragmentShader,
  }
  material.onBeforeCompile(shader as unknown as THREE.WebGLProgramParametersWithUniforms, {} as THREE.WebGLRenderer)
  return shader
}

function meshed(request: MeshRequest): WorkerResponse {
  return {
    type: 'meshed', key: request.key, cx: request.cx, cz: request.cz, version: request.version,
    base: new Uint8Array(16 * 16 * 128), mesh: { opaque: oneQuad(), cutout: empty(), translucent: empty() }, ms: 2,
  }
}

function setup() {
  const store = new WorldStore('1')
  const group = new THREE.Group()
  const worker = new FakeWorker()
  const onError = vi.fn()
  const renderer = new ColumnRenderer(store, group, onError, worker as unknown as Worker)
  return { store, group, worker, onError, renderer }
}

describe('applyDaylight', () => {
  it('darkens terrain color by daylight except where a vertex glows', () => {
    const daylight = { value: 0.35 }
    const material = new THREE.MeshBasicMaterial({ vertexColors: true })
    applyDaylight(material, daylight)
    const shader = compile(material)
    expect(shader.uniforms.uDaylight).toBe(daylight)
    expect(shader.vertexShader).toContain('attribute float glow;')
    expect(shader.vertexShader).toContain('vGlow = glow;')
    expect(shader.fragmentShader).toContain('uniform float uDaylight;')
    expect(shader.fragmentShader).toContain('diffuseColor.rgb *= mix(uDaylight, 1.0, vGlow);')
    expect(material.customProgramCacheKey()).toBe('terrain-daylight')
  })
})

describe('ColumnRenderer', () => {
  it('requests the nearest columns first and caps work in flight', () => {
    const { worker, renderer } = setup()
    renderer.setView(8, 8, 1)
    expect(worker.posted).toHaveLength(MAX_IN_FLIGHT)
    expect(worker.posted[0].key).toBe('0,0')
    // Each reply frees a slot, so the list grows while we answer it.
    for (let i = 0; i < worker.posted.length; i++) worker.reply(meshed(worker.posted[i]))
    expect(worker.posted).toHaveLength(9)
  })

  it('adds meshes for non-empty layers and remembers the base column', () => {
    const { store, group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    const response = meshed(worker.posted[0])
    if (response.type === 'meshed') response.base[0] = 42
    worker.reply(response)
    expect(group.children).toHaveLength(1)
    expect(store.getBlock(0, -8, 0)).toBe(42)
    expect(renderer.stats()).toMatchObject({ columns: 1, pending: 0, lastMeshMs: 2 })
  })

  it('ignores a stale reply after a block change', () => {
    const { store, group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    store.applyServerChanges([{ x: 3, y: 30, z: 3, material: 'stone' }])
    expect(worker.posted.map((request) => request.version)).toEqual([1, 2])
    worker.reply(meshed(worker.posted[0]))
    expect(group.children).toHaveLength(0)
    worker.reply(meshed(worker.posted[1]))
    expect(group.children).toHaveLength(1)
  })

  it('retries a failed column once, then logs', () => {
    const { worker, renderer } = setup()
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderer.setView(8, 8, 0)
    worker.reply({ type: 'error', key: '0,0', version: 1, message: 'boom' })
    expect(worker.posted).toHaveLength(2)
    worker.reply({ type: 'error', key: '0,0', version: 2, message: 'boom' })
    expect(worker.posted).toHaveLength(2)
    expect(log).toHaveBeenCalledOnce()
    log.mockRestore()
  })

  it('ignores a reply from before a column was unloaded and reloaded', () => {
    const { group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    const staleRequest = worker.posted[0]
    renderer.setView(8 + 16 * 5, 8, 0) // move away: unloads '0,0', loads '5,0'
    renderer.setView(8, 8, 0) // move back: unloads '5,0', reloads '0,0' fresh
    const freshRequest = worker.posted.at(-1)!
    expect(freshRequest.key).toBe('0,0')
    worker.reply(meshed(staleRequest))
    expect(group.children).toHaveLength(0)
    worker.reply(meshed(freshRequest))
    expect(group.children).toHaveLength(1)
  })

  it('unloads columns that fall out of range', () => {
    const { group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    worker.reply(meshed(worker.posted[0]))
    renderer.setView(8 + 16 * 5, 8, 0)
    expect(group.children).toHaveLength(0)
    expect(worker.posted.at(-1)?.key).toBe('5,0')
  })

  it('installs the glow attribute and drives the terrain daylight uniform', () => {
    const { group, worker, renderer } = setup()
    renderer.setView(8, 8, 0)
    worker.reply(meshed(worker.posted[0]))
    const mesh = group.children[0] as THREE.Mesh
    expect(mesh.geometry.getAttribute('glow').itemSize).toBe(1)
    renderer.setDaylight(0.35)
    const shader = compile(mesh.material as THREE.Material)
    expect(shader.uniforms.uDaylight.value).toBe(0.35)
    renderer.setDaylight(4)
    expect(shader.uniforms.uDaylight.value).toBe(1)
  })

  it('reports a worker crash and cleans up on dispose', () => {
    const { group, worker, onError, renderer } = setup()
    renderer.setView(8, 8, 0)
    worker.reply(meshed(worker.posted[0]))
    worker.onerror?.({ preventDefault() {} } as ErrorEvent)
    expect(onError).toHaveBeenCalledOnce()
    renderer.dispose()
    expect(worker.terminated).toBe(true)
    expect(group.children).toHaveLength(0)
  })
})
