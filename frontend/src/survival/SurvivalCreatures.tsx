import { useLayoutEffect, useMemo, useRef, type RefObject } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Voxel } from '../types/world'
import { creatureModel, dropColor } from './creatures'
import { dropPops, drawn, healthBar, lookAt, movesById, placeAt, puffAge } from './creatureMotion'
import { puffBits } from './effects'
import type { Creature, CreatureMove } from './types'

/** Creatures drawn at most: the nearest ones, as the server lists them. */
const MAX_DRAWN = 32
const PUFF_BITS = 6
const MOST_DROPS = 4
const BAR_WIDTH = 0.7
const FISH_LIFT = 0.3
const PUFF_COLOR = '#f4f1ea'
const BAR_BACK = '#3b2f2f'
const BAR_FILL = '#79c46b'
const HIDDEN: Creature[] = []

/** One part's voxels as an instanced mesh of unit cubes, colored per voxel, like PetVoxels, with its
 * material in `material` so the hurt flash can light it up. */
function Voxels({ voxels, material }: { voxels: Voxel[]; material: RefObject<THREE.MeshStandardMaterial | null> }) {
  const mesh = useRef<THREE.InstancedMesh>(null)

  useLayoutEffect(() => {
    const cubes = mesh.current
    if (!cubes) return
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    voxels.forEach((voxel, index) => {
      dummy.position.set(voxel.x + 0.5, voxel.y + 0.5, voxel.z + 0.5)
      dummy.updateMatrix()
      cubes.setMatrixAt(index, dummy.matrix)
      color.setRGB(voxel.r / 255, voxel.g / 255, voxel.b / 255, THREE.SRGBColorSpace)
      cubes.setColorAt(index, color)
    })
    cubes.instanceMatrix.needsUpdate = true
    if (cubes.instanceColor) cubes.instanceColor.needsUpdate = true
  }, [voxels])

  if (voxels.length === 0) return null
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, voxels.length]} frustumCulled={false}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial ref={material} roughness={0.55} metalness={0.05} />
    </instancedMesh>
  )
}

function flashRed(material: THREE.MeshStandardMaterial | null, flash: number) {
  material?.emissive.setRGB(0.9 * flash, 0.12 * flash, 0.1 * flash)
}

/**
 * One creature: its voxel model walking its last move with a hop and bob, grazing head down, a red
 * flash and a knock back when hit with its health bar over it for a few seconds, and when it dies
 * it tips over and puffs away as its drops pop out. All per-frame work happens in useFrame.
 */
function CreatureFigure({ creature, move, now }: { creature: Creature; move: CreatureMove | undefined; now: () => number }) {
  const model = creatureModel(creature.kind)
  const low = Math.min(...[...model.body, ...model.head].map((voxel) => voxel.y))
  const height = (Math.max(...[...model.body, ...model.head].map((voxel) => voxel.y)) - low + 1) * model.scale
  const colors = useMemo(() => (creature.drops ?? []).slice(0, MOST_DROPS).map((item) => {
    const [r, g, b] = dropColor(item)
    return new THREE.Color().setRGB(r / 255, g / 255, b / 255, THREE.SRGBColorSpace)
  }), [creature.drops])
  const root = useRef<THREE.Group>(null)
  const body = useRef<THREE.Group>(null)
  const head = useRef<THREE.Group>(null)
  const bodyMaterial = useRef<THREE.MeshStandardMaterial>(null)
  const headMaterial = useRef<THREE.MeshStandardMaterial>(null)
  const bar = useRef<THREE.Group>(null)
  const fill = useRef<THREE.Mesh>(null)
  const puff = useRef<THREE.InstancedMesh>(null)
  const pops = useRef<THREE.Group>(null)
  const scratch = useRef<THREE.Object3D | null>(null)

  useFrame((state) => {
    const group = root.current
    if (!group) return
    const t = now()
    group.visible = drawn(creature, t)
    if (!group.visible) return
    const place = placeAt(creature, move, t)
    const look = lookAt(creature, place, t, state.clock.elapsedTime, model.hop)
    const lift = creature.kind === 'fish' ? FISH_LIFT : 0
    group.position.set(place.x + 0.5 + Math.sin(place.facing) * look.knock, place.y + lift + look.lift,
      place.z + 0.5 + Math.cos(place.facing) * look.knock)
    group.rotation.y = place.facing
    body.current?.rotation.set(look.pitch, 0, look.roll)
    body.current?.scale.setScalar(Math.max(0.001, look.size))
    if (head.current) head.current.rotation.x = look.headPitch
    flashRed(bodyMaterial.current, look.flash)
    flashRed(headMaterial.current, look.flash)

    const health = healthBar(creature, t)
    if (bar.current) {
      bar.current.visible = health.shown
      if (health.shown) {
        // Keep the bar square to the camera whichever way the creature faces.
        bar.current.quaternion.copy(group.quaternion).invert().multiply(state.camera.quaternion)
        fill.current?.scale.set(Math.max(0.001, health.fraction), 1, 1)
        fill.current?.position.set((health.fraction - 1) * BAR_WIDTH / 2, 0, 0.01)
      }
    }

    const age = puffAge(creature, t)
    const bits = puff.current
    if (bits) {
      bits.visible = age !== null
      if (age !== null) {
        const dummy = (scratch.current ??= new THREE.Object3D())
        const { offsets, scale } = puffBits(PUFF_BITS, age)
        offsets.forEach((offset, index) => {
          dummy.position.set(offset.x, height / 2 + offset.y, offset.z)
          dummy.scale.setScalar(scale)
          dummy.updateMatrix()
          bits.setMatrixAt(index, dummy.matrix)
        })
        bits.instanceMatrix.needsUpdate = true
      }
    }
    const popped = pops.current
    if (popped) {
      popped.visible = age !== null
      if (age !== null) {
        dropPops(creature.drops?.slice(0, MOST_DROPS), age).forEach((pop, index) => {
          popped.children[index]?.position.set(pop.offset.x, pop.offset.y, pop.offset.z)
          popped.children[index]?.scale.setScalar(pop.scale)
        })
      }
    }
  })

  const neck: [number, number, number] = [model.neck.x, model.neck.y, model.neck.z]
  return (
    <group ref={root} visible={false}>
      <group ref={body}>
        <group scale={model.scale} position={[-0.5 * model.scale, -low * model.scale, -0.5 * model.scale]}>
          <Voxels voxels={model.body} material={bodyMaterial} />
          <group ref={head} position={neck}>
            <group position={[-neck[0], -neck[1], -neck[2]]}>
              <Voxels voxels={model.head} material={headMaterial} />
            </group>
          </group>
        </group>
      </group>
      <group ref={bar} position={[0, height + 0.3, 0]} visible={false}>
        <mesh>
          <boxGeometry args={[BAR_WIDTH, 0.09, 0.02]} />
          <meshBasicMaterial color={BAR_BACK} />
        </mesh>
        <mesh ref={fill}>
          <boxGeometry args={[BAR_WIDTH, 0.07, 0.02]} />
          <meshBasicMaterial color={BAR_FILL} />
        </mesh>
      </group>
      <instancedMesh ref={puff} args={[undefined, undefined, PUFF_BITS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[0.16, 0.16, 0.16]} />
        <meshLambertMaterial color={PUFF_COLOR} />
      </instancedMesh>
      <group ref={pops} visible={false}>
        {colors.map((color, index) => (
          <mesh key={index}>
            <boxGeometry args={[0.18, 0.18, 0.18]} />
            <meshLambertMaterial color={color} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

/** The creatures near Mimo (the snapshot's list, nearest first), drawn at `now` (the replay time). */
export default function SurvivalCreatures({ creatures, moves, now }: {
  creatures: Creature[] | undefined
  moves: CreatureMove[] | undefined
  now: () => number
}) {
  const byId = useMemo(() => movesById(moves), [moves])
  const shown = (creatures ?? HIDDEN).slice(0, MAX_DRAWN)
  return (
    <>
      {shown.map((creature) => (
        <CreatureFigure key={creature.id} creature={creature} move={byId.get(creature.id)} now={now} />
      ))}
    </>
  )
}
