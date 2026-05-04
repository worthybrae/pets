import { Canvas } from '@react-three/fiber'
import type { Chunk, PetEntity as PetEntityType } from '../../types/world'
import WorldManager from './WorldManager'
import PetEntity from './PetEntity'
import CameraController from './CameraController'

interface WorldSceneProps {
  chunks: Chunk[]
  pet: PetEntityType
  onVoxelClick?: (metadataId: string) => void
  onPetPositionChange?: (pos: { x: number; y: number; z: number }) => void
}

export default function WorldScene({ chunks, pet, onVoxelClick, onPetPositionChange }: WorldSceneProps) {
  return (
    <div className="h-screen w-screen bg-[#e5e5e5]">
      <Canvas
        camera={{ position: [10, 8, 10], fov: 50, near: 0.1, far: 500 }}
        gl={{ antialias: true }}
        scene={{ background: undefined }}
      >
        {/* Black void background */}
        <color attach="background" args={['#e5e5e5']} />

        {/* Lighting — Math.PI base for physically correct lights in Three.js 0.184 */}
        <ambientLight intensity={Math.PI * 0.8} />
        <directionalLight
          position={[20, 30, 10]}
          intensity={Math.PI * 1.5}
          castShadow={false}
        />
        <directionalLight
          position={[-10, 10, -10]}
          intensity={Math.PI * 0.5}
        />

        {/* Fog — pushed far back so nearby world items stay visible */}
        <fog attach="fog" args={['#e5e5e5', 100, 200]} />

        {/* World chunks */}
        <WorldManager
          chunks={chunks}
          onVoxelClick={onVoxelClick}
        />

        {/* Pet */}
        <PetEntity pet={pet} onPositionChange={onPetPositionChange} />

        {/* Camera */}
        <CameraController petPosition={pet.position} />
      </Canvas>
    </div>
  )
}
