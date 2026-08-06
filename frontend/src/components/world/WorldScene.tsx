import { Canvas } from '@react-three/fiber'
import type { Chunk, PetEntity as PetEntityType } from '../../types/world'
import type { WorldCollider } from './physics'
import WorldManager from './WorldManager'
import PetEntity from './PetEntity'
import CameraController from './CameraController'

interface WorldSceneProps {
  chunks: Chunk[]
  pet: PetEntityType
  petThought?: string | null
  collider?: WorldCollider
  onVoxelClick?: (metadataId: string) => void
  onPetPositionChange?: (pos: { x: number; y: number; z: number }) => void
}

export default function WorldScene({ chunks, pet, petThought, collider, onVoxelClick, onPetPositionChange }: WorldSceneProps) {
  return (
    <div className="h-screen w-screen bg-[#87CEEB]">
      <Canvas
        camera={{ position: [22, 20, 22], fov: 50, near: 0.1, far: 500 }}
        gl={{ antialias: true }}
        scene={{ background: undefined }}
      >
        {/* Sky background */}
        <color attach="background" args={['#87CEEB']} />

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

        {/* Fog — blends into sky at distance */}
        <fog attach="fog" args={['#87CEEB', 80, 180]} />

        {/* World chunks */}
        <WorldManager
          chunks={chunks}
          viewDistance={5}
          onVoxelClick={onVoxelClick}
        />

        {/* Pet */}
        <PetEntity pet={pet} thought={petThought} collider={collider} onPositionChange={onPetPositionChange} />

        {/* Camera */}
        <CameraController petPosition={pet.position} />
      </Canvas>
    </div>
  )
}
