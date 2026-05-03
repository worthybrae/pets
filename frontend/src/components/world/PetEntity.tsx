import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { PetEntity as PetEntityType } from '../../types/world'

interface PetEntityProps {
  pet: PetEntityType
}

export default function PetEntity({ pet }: PetEntityProps) {
  const groupRef = useRef<THREE.Group>(null)
  const meshRef = useRef<THREE.InstancedMesh>(null)
  const timeRef = useRef(0)
  const initializedRef = useRef(false)
  const prevVoxelsRef = useRef(pet.voxels)

  // Setup instanced mesh matrices/colors inside useFrame
  // so the ref is guaranteed to be available
  useFrame((_, delta) => {
    timeRef.current += delta

    if (meshRef.current && (!initializedRef.current || prevVoxelsRef.current !== pet.voxels)) {
      const mesh = meshRef.current
      const dummy = new THREE.Object3D()
      const color = new THREE.Color()

      for (let i = 0; i < pet.voxels.length; i++) {
        const v = pet.voxels[i]
        dummy.position.set(v.x + 0.5, v.y + 0.5, v.z + 0.5)
        dummy.updateMatrix()
        mesh.setMatrixAt(i, dummy.matrix)
        color.setRGB(v.r / 255, v.g / 255, v.b / 255)
        mesh.setColorAt(i, color)
      }
      mesh.instanceMatrix.needsUpdate = true
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
      initializedRef.current = true
      prevVoxelsRef.current = pet.voxels
    }

    // Idle animation: gentle bob
    if (groupRef.current) {
      groupRef.current.position.y = pet.position.y + Math.sin(timeRef.current * 2) * 0.1
    }
  })

  if (pet.voxels.length === 0) return null

  return (
    <group
      ref={groupRef}
      position={[pet.position.x, pet.position.y, pet.position.z]}
    >
      <pointLight color="#ffffff" intensity={2} distance={15} decay={2} />
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, pet.voxels.length]}
        frustumCulled={false}
      >
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial
          vertexColors
          toneMapped={false}
          fog={false}
        />
      </instancedMesh>
    </group>
  )
}
