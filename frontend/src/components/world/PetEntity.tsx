import { useRef, useMemo } from 'react'
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

  useMemo(() => {
    if (!meshRef.current) return
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
  }, [pet.voxels])

  // Idle animation: gentle bob
  useFrame((_, delta) => {
    timeRef.current += delta
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
      <instancedMesh
        ref={meshRef}
        args={[undefined, undefined, pet.voxels.length]}
        frustumCulled={false}
      >
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial
          vertexColors
          emissive={new THREE.Color(0.15, 0.15, 0.15)}
          emissiveIntensity={1}
        />
      </instancedMesh>
    </group>
  )
}
