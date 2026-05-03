import { useRef, useEffect, useCallback, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import type { OrbitControls as OrbitControlsType } from 'three/addons/controls/OrbitControls.js'

interface CameraControllerProps {
  petPosition: { x: number; y: number; z: number }
  followDistance?: number
}

export default function CameraController({
  petPosition,
  followDistance = 12,
}: CameraControllerProps) {
  const controlsRef = useRef<OrbitControlsType>(null)
  const { camera } = useThree()
  const [isFollowing, setIsFollowing] = useState(true)
  const keysRef = useRef<Set<string>>(new Set())
  const targetRef = useRef(new THREE.Vector3(petPosition.x, petPosition.y, petPosition.z))
  const cameraOffsetRef = useRef(new THREE.Vector3(followDistance * 0.6, followDistance * 0.6, followDistance * 0.6))

  // Keyboard input handling
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      keysRef.current.add(e.key.toLowerCase())
      // Any movement key breaks follow mode
      if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(e.key.toLowerCase())) {
        setIsFollowing(false)
      }
    }
    const handleKeyUp = (e: KeyboardEvent) => {
      keysRef.current.delete(e.key.toLowerCase())
    }
    const handleDblClick = () => {
      setIsFollowing(true)
    }

    window.addEventListener('keydown', handleKeyDown)
    window.addEventListener('keyup', handleKeyUp)
    window.addEventListener('dblclick', handleDblClick)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      window.removeEventListener('keyup', handleKeyUp)
      window.removeEventListener('dblclick', handleDblClick)
    }
  }, [])

  // Detect user orbit interaction (breaks follow mode)
  const handleControlStart = useCallback(() => {
    setIsFollowing(false)
  }, [])

  useFrame((_, delta) => {
    const keys = keysRef.current
    const moveSpeed = 15 * delta

    // WASD / Arrow key movement
    if (keys.size > 0 && controlsRef.current) {
      const forward = new THREE.Vector3()
      camera.getWorldDirection(forward)
      forward.y = 0
      forward.normalize()
      const right = new THREE.Vector3().crossVectors(forward, camera.up).normalize()

      const movement = new THREE.Vector3()
      if (keys.has('w') || keys.has('arrowup')) movement.add(forward)
      if (keys.has('s') || keys.has('arrowdown')) movement.sub(forward)
      if (keys.has('d') || keys.has('arrowright')) movement.add(right)
      if (keys.has('a') || keys.has('arrowleft')) movement.sub(right)

      if (movement.length() > 0) {
        movement.normalize().multiplyScalar(moveSpeed)
        camera.position.add(movement)
        controlsRef.current.target.add(movement)
      }
    }

    // Follow pet mode
    if (isFollowing) {
      const petPos = new THREE.Vector3(petPosition.x, petPosition.y, petPosition.z)
      targetRef.current.lerp(petPos, 3 * delta)

      const desiredCameraPos = targetRef.current.clone().add(cameraOffsetRef.current)
      camera.position.lerp(desiredCameraPos, 3 * delta)

      if (controlsRef.current) {
        controlsRef.current.target.lerp(targetRef.current, 3 * delta)
      }
    }
  })

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.1}
      minDistance={3}
      maxDistance={100}
      onStart={handleControlStart}
    />
  )
}
