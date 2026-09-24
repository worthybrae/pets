import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { arrowAt } from './archery'
import { creatureModel } from './creatures'
import { FLAME_BITS, flames } from './hostileMotion'
import { replayAt } from './replay'
import type { Creature, FinishedAction, MimoAction, Point } from './types'

/** Burning creatures drawn at most (the hostile cap is 8). */
const MOST_BURNING = 8
const SHAFT: [number, number, number] = [0.04, 0.04, 0.7]
const TIP: [number, number, number] = [0.08, 0.08, 0.12]
const FLAME_SIZE = 0.16
const NONE: Creature[] = []

/**
 * L2's fighting, drawn REPLAY_DELAY behind the server like the pet: the arrow of a shot in flight
 * from the pet to its target (archery.ts), and flames over each hostile burning in the sun
 * (hostileMotion.ts; a burning creature stands still, where the snapshot has it). All per-frame
 * work is in useFrame; nothing here sets React state.
 */
export default function CombatEffects({ action, recent, position, creatures = NONE, now }: {
  action: MimoAction | null
  recent: FinishedAction[]
  position: Point
  creatures?: Creature[]
  now: () => number
}) {
  const arrow = useRef<THREE.Group>(null)
  const fire = useRef<THREE.InstancedMesh>(null)
  const scratch = useRef<THREE.Object3D | null>(null)

  useFrame(() => {
    const t = now()
    const flight = arrow.current
    if (flight) {
      const { step, rest } = replayAt(action, recent, position, t)
      const pose = arrowAt(step, rest, t)
      flight.visible = pose !== null
      if (pose) {
        flight.position.set(pose.x, pose.y, pose.z)
        flight.rotation.set(-pose.pitch, pose.yaw, 0, 'YXZ')
      }
    }
    const bits = fire.current
    if (!bits) return
    const dummy = (scratch.current ??= new THREE.Object3D())
    let count = 0
    for (const creature of creatures.filter((found) => found.state === 'burning').slice(0, MOST_BURNING)) {
      const model = creatureModel(creature.kind)
      const ys = [...model.body, ...model.head].map((voxel) => voxel.y)
      const height = (Math.max(...ys) - Math.min(...ys) + 1) * model.scale
      for (const bit of flames(creature, t, height)) {
        dummy.position.set(creature.x + 0.5 + bit.x, creature.y + bit.y, creature.z + 0.5 + bit.z)
        dummy.scale.setScalar(FLAME_SIZE * bit.scale)
        dummy.updateMatrix()
        bits.setMatrixAt(count++, dummy.matrix)
      }
    }
    bits.count = count
    bits.visible = count > 0
    bits.instanceMatrix.needsUpdate = true
  })

  return (
    <>
      <group ref={arrow} visible={false}>
        <mesh>
          <boxGeometry args={SHAFT} />
          <meshLambertMaterial color="#b58a5a" />
        </mesh>
        <mesh position={[0, 0, SHAFT[2] / 2]}>
          <boxGeometry args={TIP} />
          <meshLambertMaterial color="#8e979a" />
        </mesh>
        <mesh position={[0, 0, -SHAFT[2] / 2]}>
          <boxGeometry args={[0.12, 0.02, 0.1]} />
          <meshLambertMaterial color="#f4f1ea" />
        </mesh>
      </group>
      <instancedMesh ref={fire} args={[undefined, undefined, MOST_BURNING * FLAME_BITS]} visible={false} frustumCulled={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color="#ffa53d" />
      </instancedMesh>
    </>
  )
}
