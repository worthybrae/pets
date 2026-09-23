import { useLayoutEffect, useRef } from 'react'
import * as THREE from 'three'
import type { Voxel } from '../../types/world'

/** A pet's voxels as one instanced mesh of unit cubes, colored per voxel. */
export default function PetVoxels({ voxels }: { voxels: Voxel[] }) {
  const meshRef = useRef<THREE.InstancedMesh>(null)

  useLayoutEffect(() => {
    const mesh = meshRef.current
    if (!mesh) return
    const dummy = new THREE.Object3D()
    const color = new THREE.Color()
    voxels.forEach((voxel, index) => {
      dummy.position.set(voxel.x + 0.5, voxel.y + 0.5, voxel.z + 0.5)
      dummy.updateMatrix()
      mesh.setMatrixAt(index, dummy.matrix)
      color.setRGB(voxel.r / 255, voxel.g / 255, voxel.b / 255, THREE.SRGBColorSpace)
      mesh.setColorAt(index, color)
    })
    mesh.instanceMatrix.needsUpdate = true
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true
  }, [voxels])

  if (voxels.length === 0) return null
  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, voxels.length]} frustumCulled={false}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial roughness={0.4} metalness={0.1} />
    </instancedMesh>
  )
}
