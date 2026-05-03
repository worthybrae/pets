import { useState, useCallback } from 'react'
import WorldScene from '../components/world/WorldScene'
import AppLayout from '../components/layout/AppLayout'
import { useChat } from '../hooks/useChat'
import type { VoxelUpdate, Position } from '../hooks/useWebSocket'
import type { Chunk, PetEntity as PetEntityType, Voxel } from '../types/world'

interface Pet {
  id: string
  name: string
  seed_curiosity: string
  food_balance: number
}

// A new pet's world: empty void
const emptyWorld: Chunk[] = []

// A new pet: single white voxel
const newPet: PetEntityType = {
  position: { x: 0, y: 0, z: 0 },
  voxels: [{ x: 0, y: 0, z: 0, r: 255, g: 255, b: 255, a: 255 }],
}

export default function World({ pet }: { pet: Pet }) {
  const [currentTime, setCurrentTime] = useState<Date>(new Date())
  const [chunks, setChunks] = useState<Chunk[]>(emptyWorld)
  const [petEntity, setPetEntity] = useState<PetEntityType>(newPet)
  const [foodBalance, setFoodBalance] = useState(pet.food_balance)

  const handleVoxelUpdate = useCallback((update: VoxelUpdate) => {
    setChunks((prevChunks) => {
      const newChunks = [...prevChunks]
      if (update.action === 'place') {
        const newVoxels: Voxel[] = update.voxels.map((v) => ({
          x: v.x, y: v.y, z: v.z,
          r: v.r ?? 255, g: v.g ?? 255, b: v.b ?? 255, a: v.a ?? 255,
        }))
        if (newChunks.length > 0) {
          newChunks[0] = { ...newChunks[0], voxels: [...newChunks[0].voxels, ...newVoxels] }
        } else {
          newChunks.push({ chunk_x: 0, chunk_y: 0, chunk_z: 0, voxels: newVoxels })
        }
      } else if (update.action === 'remove') {
        const removeSet = new Set(update.voxels.map((v) => `${v.x},${v.y},${v.z}`))
        for (let i = 0; i < newChunks.length; i++) {
          newChunks[i] = {
            ...newChunks[i],
            voxels: newChunks[i].voxels.filter((v) => !removeSet.has(`${v.x},${v.y},${v.z}`)),
          }
        }
      }
      return newChunks
    })
  }, [])

  const handlePetMoved = useCallback((position: Position) => {
    setPetEntity((prev) => ({ ...prev, position }))
  }, [])

  const handleFoodUpdate = useCallback((balance: number) => {
    setFoodBalance(balance)
  }, [])

  const { messages, sendMessage, isConnected } = useChat({
    petId: pet.id,
    petName: pet.name,
    onVoxelUpdate: handleVoxelUpdate,
    onPetMoved: handlePetMoved,
    onFoodUpdate: handleFoodUpdate,
  })

  const handleVoxelClick = (metadataId: string) => {
    console.log('Artifact clicked:', metadataId)
  }

  return (
    <AppLayout
      petName={pet.name}
      foodBalance={foodBalance}
      maxFood={100}
      messages={messages}
      onSendMessage={sendMessage}
      onTimeChange={setCurrentTime}
      currentTime={currentTime}
    >
      <WorldScene chunks={chunks} pet={petEntity} onVoxelClick={handleVoxelClick} />
      <div className="fixed bottom-4 left-4 z-50 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse'}`} />
        <span className="text-xs text-white/40">
          {isConnected ? 'Live' : 'Offline'}
        </span>
      </div>
    </AppLayout>
  )
}
