import { useEffect, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { blockDef } from '../engine/blocks'
import type { WorldStore } from '../engine/worldStore'
import { doorAxis, doorSwing, heldOpen } from './doors'
import type { Point } from './types'

/** Doors drawn at most, the nearest first, and how far from the pet they are looked for. */
const MOST_DOORS = 8
const DOOR_REACH = 32
/** Seconds between looks for doors when nothing changed in the store. */
const LOOK_EVERY = 2
const PANEL: [number, number, number] = [1, 2, 0.12]
const PLANK = '#8f6a45'
const TRIM = '#6b4a2e'

interface Door {
  cell: Point
  axis: 'x' | 'z'
}

/**
 * The doors near the pet (L2): a two-block plank door in each door block's cell (the mesher draws
 * none, shared/blocks.json layer "none"), hinged on one side and swinging open while the pet drawn
 * at `pet()` passes (doors.ts); in an archive, with no pet to replay, they stay shut. The doors are
 * looked up again when the store changes or every LOOK_EVERY seconds, all inside useFrame.
 */
export default function SurvivalDoors({ store, focus, pet, held }: {
  store: WorldStore
  focus: Point
  pet?: () => Point | null
  /** Making: the doors a machine holds open ([x, y, z]); they stand wide open. */
  held?: readonly number[][]
}) {
  const hinges = useRef<(THREE.Group | null)[]>([])
  const doors = useRef<Door[]>([])
  const looked = useRef({ dirty: true, at: -Infinity })

  useEffect(() => store.subscribe(() => { looked.current.dirty = true }), [store])

  useFrame((state) => {
    const clock = state.clock.elapsedTime
    if (looked.current.dirty || clock - looked.current.at > LOOK_EVERY) {
      const solidAt = (x: number, y: number, z: number) => blockDef(store.getBlock(x, y, z)).solid
      doors.current = store.placedCells('door', focus.x, focus.z, DOOR_REACH)
        .sort((a, b) => Math.hypot(a.x - focus.x, a.z - focus.z) - Math.hypot(b.x - focus.x, b.z - focus.z))
        .slice(0, MOST_DOORS)
        .map((cell) => ({ cell, axis: doorAxis(solidAt, cell) }))
      looked.current = { dirty: false, at: clock }
    }
    const drawn = pet?.() ?? null
    hinges.current.forEach((hinge, index) => {
      if (!hinge) return
      const door = doors.current[index]
      hinge.visible = door !== undefined
      if (!door) return
      const { x, y, z } = door.cell
      const swing = (heldOpen(door.cell, held) ? 1 : doorSwing(door.cell, drawn)) * (Math.PI / 2)
      if (door.axis === 'x') {
        hinge.position.set(x, y, z + 0.5)
        hinge.rotation.y = swing
      } else {
        hinge.position.set(x + 0.5, y, z)
        hinge.rotation.y = -Math.PI / 2 + swing
      }
    })
  })

  return (
    <>
      {Array.from({ length: MOST_DOORS }, (_, index) => (
        <group key={index} ref={(group) => { hinges.current[index] = group }} visible={false}>
          <mesh position={[PANEL[0] / 2, PANEL[1] / 2, 0]}>
            <boxGeometry args={PANEL} />
            <meshStandardMaterial color={PLANK} roughness={0.8} />
          </mesh>
          <mesh position={[PANEL[0] / 2, PANEL[1] / 2, 0]}>
            <boxGeometry args={[PANEL[0] * 0.92, 0.08, PANEL[2] + 0.02]} />
            <meshStandardMaterial color={TRIM} roughness={0.8} />
          </mesh>
          <mesh position={[PANEL[0] - 0.16, 1.0, PANEL[2] / 2 + 0.03]}>
            <boxGeometry args={[0.06, 0.06, 0.06]} />
            <meshStandardMaterial color="#d8c08a" metalness={0.3} />
          </mesh>
        </group>
      ))}
    </>
  )
}
