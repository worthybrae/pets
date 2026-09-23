import { useRef } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import type { OrbitControls as OrbitControlsType } from 'three-stdlib'
import * as THREE from 'three'
import { fogRange } from '../engine/fog'

interface Focus {
  x: number
  z: number
}

/** Orbit controls that glide after a focus point, keep the fog past it and report chunk changes. */
export default function FollowCamera({ focus, focusY, initialFocus, initialFocusY, distance, follow, viewDistance, onOrbit, onChunkChange }: {
  focus: Focus
  focusY: number
  initialFocus: Focus
  initialFocusY: number
  distance: number
  follow: boolean
  viewDistance: number
  onOrbit: () => void
  onChunkChange: (x: number, z: number) => void
}) {
  const controlsRef = useRef<OrbitControlsType>(null)
  const lastChunk = useRef('')
  const { camera } = useThree()

  useFrame((state, delta) => {
    const controls = controlsRef.current
    if (!controls) return
    if (follow) {
      const desired = new THREE.Vector3(focus.x, focusY, focus.z)
      const movement = desired.sub(controls.target).multiplyScalar(1 - Math.exp(-3 * delta))
      controls.target.add(movement)
      camera.position.add(movement)
      const offset = camera.position.clone().sub(controls.target)
      const currentDistance = offset.length()
      camera.position.addScaledVector(offset.normalize(), (distance - currentDistance) * (1 - Math.exp(-2 * delta)))
      controls.update()
    }
    // Fog follows the live camera distance, so zooming out does not fade Mimo into fog early.
    const fog = state.scene.fog
    if (fog instanceof THREE.Fog) {
      const [near, far] = fogRange(viewDistance, camera.position.distanceTo(controls.target))
      fog.near = near
      fog.far = far
    }
    const cx = Math.floor(controls.target.x / 16)
    const cz = Math.floor(controls.target.z / 16)
    const key = `${cx},${cz}`
    if (key !== lastChunk.current) {
      lastChunk.current = key
      onChunkChange(cx, cz)
    }
  })

  return (
    <OrbitControls ref={controlsRef} target={[initialFocus.x, initialFocusY, initialFocus.z]}
      enableDamping dampingFactor={0.08} minDistance={11} maxDistance={130}
      maxPolarAngle={Math.PI / 2.04} onStart={onOrbit} />
  )
}
