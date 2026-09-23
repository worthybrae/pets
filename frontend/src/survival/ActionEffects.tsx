import { useEffect, useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { blockDef, blockId } from '../engine/blocks'
import type { WorldStore } from '../engine/worldStore'
import {
  BURST_SECONDS, CRACK_STAGES, PLACE_BOUNCE_SECONDS, POP_SECONDS, blockEffects, burst, crackStage, crackTexels,
  itemPop, placeScale, type BlockEffect,
} from './effects'
import { poseAt } from './motion'
import type { FinishedAction, MimoAction, Point } from './types'

const PARTICLES = 8
/** How long a break waits for block sync to remove the block before it plays anyway. */
const BREAK_WAIT = 2
/** How long a placed block's stand-in waits for block sync to deliver the real block. */
const GHOST_WAIT = 3
const CRACK_SIZE = 1.01
/** Fired keys are trimmed to the current steps once there are this many. */
const FIRED_LIMIT = 64

interface Playing {
  effect: BlockEffect
  /** Server time the animation began. */
  from: number
}

function paint(material: THREE.MeshLambertMaterial | null, block: string) {
  if (!material) return
  const [r, g, b] = blockDef(blockId(block)).color
  material.color.setRGB(r / 255, g / 255, b / 255, THREE.SRGBColorSpace)
}

function crackTexture(stage: number): THREE.DataTexture {
  const texture = new THREE.DataTexture(crackTexels(stage), 8, 8, THREE.RGBAFormat)
  texture.magFilter = THREE.NearestFilter
  texture.minFilter = THREE.NearestFilter
  texture.colorSpace = THREE.SRGBColorSpace
  texture.needsUpdate = true
  return texture
}

function center(cell: Point): Point {
  return { x: cell.x + 0.5, y: cell.y + 0.5, z: cell.z + 0.5 }
}

/**
 * Block effects of Mimo's steps: cracks on the block being mined, particles and an item that pops
 * to the pet when block sync removes a mined block, and a bounce when a block is placed.
 */
export default function ActionEffects({ store, action, recent, position, now }: {
  store: WorldStore
  action: MimoAction | null
  recent: FinishedAction[]
  position: Point
  /** Server time now, in seconds. */
  now: () => number
}) {
  const effects = useMemo(() => blockEffects(action, recent), [action, recent])
  const textures = useRef<THREE.DataTexture[]>([])
  const crack = useRef<THREE.Mesh>(null)
  const crackMaterial = useRef<THREE.MeshBasicMaterial>(null)
  const particles = useRef<THREE.InstancedMesh>(null)
  const particleMaterial = useRef<THREE.MeshLambertMaterial>(null)
  const pop = useRef<THREE.Mesh>(null)
  const popMaterial = useRef<THREE.MeshLambertMaterial>(null)
  const ghost = useRef<THREE.Mesh>(null)
  const ghostMaterial = useRef<THREE.MeshLambertMaterial>(null)
  const scratch = useRef<THREE.Object3D | null>(null)
  const fired = useRef(new Set<string>())
  const openedAt = useRef<number | null>(null)
  const breaking = useRef<Playing | null>(null)
  const placing = useRef<Playing | null>(null)

  useEffect(() => {
    const made = Array.from({ length: CRACK_STAGES + 1 }, (_, stage) => crackTexture(stage))
    textures.current = made
    return () => { for (const texture of made) texture.dispose() }
  }, [])

  useFrame(() => {
    const t = now()
    // Steps that ended before the page opened are not replayed.
    const since = (openedAt.current ??= t - 1)

    // Cracks grow on the block being mined until block sync removes it.
    const crackMesh = crack.current
    const crackMat = crackMaterial.current
    if (crackMesh && crackMat) {
      const stage = crackStage(action, t)
      const texture = textures.current[stage]
      const cell = action?.target
      const standing = action?.block !== undefined && cell !== undefined
        && store.getBlock(cell.x, cell.y, cell.z) === blockId(action.block)
      crackMesh.visible = stage > 0 && standing && texture !== undefined
      if (crackMesh.visible && cell && texture) {
        crackMesh.position.set(cell.x + 0.5, cell.y + 0.5, cell.z + 0.5)
        if (crackMat.map !== texture) {
          const hadMap = crackMat.map !== null
          crackMat.map = texture
          if (!hadMap) crackMat.needsUpdate = true
        }
      }
    }

    // Start breaks and placements when they are due.
    for (const effect of effects) {
      if (fired.current.has(effect.key) || effect.at <= since || t < effect.at) continue
      if (effect.kind === 'break') {
        const { x, y, z } = effect.cell
        const synced = store.getBlock(x, y, z) !== blockId(effect.block)
        if (!synced && t < effect.at + BREAK_WAIT) continue
        breaking.current = { effect, from: t }
        paint(particleMaterial.current, effect.block)
        paint(popMaterial.current, effect.block)
      } else {
        placing.current = { effect, from: effect.at }
        paint(ghostMaterial.current, effect.block)
      }
      fired.current.add(effect.key)
    }
    if (fired.current.size > FIRED_LIMIT) {
      const current = new Set(effects.map((effect) => effect.key))
      fired.current = new Set([...fired.current].filter((key) => current.has(key)))
    }

    // Break particles and the item flying to the pet.
    const broke = breaking.current
    const sinceBreak = broke ? t - broke.from : Infinity
    const burstMesh = particles.current
    if (burstMesh) {
      burstMesh.visible = broke !== null && sinceBreak < BURST_SECONDS
      if (burstMesh.visible && broke) {
        const dummy = (scratch.current ??= new THREE.Object3D())
        const origin = center(broke.effect.cell)
        burst(PARTICLES, sinceBreak).forEach((offset, index) => {
          dummy.position.set(origin.x + offset.x, origin.y + offset.y, origin.z + offset.z)
          dummy.scale.setScalar(1 - (0.5 * sinceBreak) / BURST_SECONDS)
          dummy.updateMatrix()
          burstMesh.setMatrixAt(index, dummy.matrix)
        })
        burstMesh.instanceMatrix.needsUpdate = true
      }
    }
    const item = pop.current
    if (item) {
      item.visible = broke !== null && sinceBreak < POP_SECONDS
      if (item.visible && broke) {
        const pet = poseAt(action, position, t)
        const flight = itemPop(sinceBreak, center(broke.effect.cell), { x: pet.x + 0.5, y: pet.y + 0.6, z: pet.z + 0.5 })
        item.position.set(flight.position.x, flight.position.y, flight.position.z)
        item.scale.setScalar(flight.scale)
      }
    }

    // A placed block bounces in until the real block arrives.
    const stand = ghost.current
    if (stand) {
      const placed = placing.current
      const sincePlace = placed ? t - placed.from : Infinity
      const cell = placed?.effect.cell
      const arrived = placed !== null && cell !== undefined
        && store.getBlock(cell.x, cell.y, cell.z) === blockId(placed.effect.block)
      stand.visible = cell !== undefined && sincePlace < GHOST_WAIT && !(arrived && sincePlace >= PLACE_BOUNCE_SECONDS)
      if (stand.visible && cell) {
        stand.position.set(cell.x + 0.5, cell.y + 0.5, cell.z + 0.5)
        stand.scale.setScalar(placeScale(sincePlace) * 1.002)
      }
    }
  })

  return (
    <>
      <mesh ref={crack} visible={false}>
        <boxGeometry args={[CRACK_SIZE, CRACK_SIZE, CRACK_SIZE]} />
        <meshBasicMaterial ref={crackMaterial} transparent depthWrite={false} />
      </mesh>
      <instancedMesh ref={particles} args={[undefined, undefined, PARTICLES]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.12, 0.12, 0.12]} />
        <meshLambertMaterial ref={particleMaterial} />
      </instancedMesh>
      <mesh ref={pop} visible={false}>
        <boxGeometry args={[0.3, 0.3, 0.3]} />
        <meshLambertMaterial ref={popMaterial} />
      </mesh>
      <mesh ref={ghost} visible={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshLambertMaterial ref={ghostMaterial} />
      </mesh>
    </>
  )
}
