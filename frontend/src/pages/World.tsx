import { useState, useCallback } from 'react'
import WorldScene from '../components/world/WorldScene'
import AppLayout from '../components/layout/AppLayout'
import { useChat } from '../hooks/useChat'
import type { VoxelUpdate, Position } from '../hooks/useWebSocket'
import { demoChunks, demoPet } from '../components/world/demoData'
import type { Chunk, PetEntity as PetEntityType, Voxel } from '../types/world'

// TODO: Replace with real pet ID from route params or auth
const PET_ID = import.meta.env.VITE_PET_ID || null

export default function World() {
  const [currentTime, setCurrentTime] = useState<Date>(new Date())
  const [chunks, setChunks] = useState<Chunk[]>(demoChunks)
  const [pet, setPet] = useState<PetEntityType>(demoPet)
  const [foodBalance, setFoodBalance] = useState(0.65)
  const [petStatus, setPetStatus] = useState<string>('idle')

  // Handle real-time voxel updates
  const handleVoxelUpdate = useCallback((update: VoxelUpdate) => {
    setChunks((prevChunks) => {
      const newChunks = [...prevChunks]

      if (update.action === 'place') {
        // Add new voxels to the first chunk (simplified; real impl would calculate chunk)
        const newVoxels: Voxel[] = update.voxels.map((v) => ({
          x: v.x,
          y: v.y,
          z: v.z,
          r: v.r ?? 255,
          g: v.g ?? 255,
          b: v.b ?? 255,
          a: v.a ?? 255,
        }))

        if (newChunks.length > 0) {
          newChunks[0] = {
            ...newChunks[0],
            voxels: [...newChunks[0].voxels, ...newVoxels],
          }
        } else {
          newChunks.push({
            chunk_x: 0,
            chunk_y: 0,
            chunk_z: 0,
            voxels: newVoxels,
          })
        }
      } else if (update.action === 'remove') {
        // Remove voxels at specified positions
        const removeSet = new Set(
          update.voxels.map((v) => `${v.x},${v.y},${v.z}`)
        )
        for (let i = 0; i < newChunks.length; i++) {
          newChunks[i] = {
            ...newChunks[i],
            voxels: newChunks[i].voxels.filter(
              (v) => !removeSet.has(`${v.x},${v.y},${v.z}`)
            ),
          }
        }
      }

      return newChunks
    })
  }, [])

  // Handle pet movement
  const handlePetMoved = useCallback((position: Position) => {
    setPet((prev) => ({
      ...prev,
      position,
    }))
  }, [])

  // Handle food updates
  const handleFoodUpdate = useCallback((balance: number) => {
    setFoodBalance(balance)
  }, [])

  // Handle status changes
  const handleStatusChange = useCallback((status: string) => {
    setPetStatus(status)
  }, [])

  // Set up chat with WebSocket integration
  const { messages, sendMessage, isConnected } = useChat({
    petId: PET_ID,
    petName: 'Pixel',
    onVoxelUpdate: handleVoxelUpdate,
    onPetMoved: handlePetMoved,
    onFoodUpdate: handleFoodUpdate,
    onStatusChange: handleStatusChange,
  })

  const handleVoxelClick = (metadataId: string) => {
    console.log('Artifact clicked:', metadataId)
  }

  const handleSendMessage = useCallback(
    (text: string) => {
      sendMessage(text)
    },
    [sendMessage]
  )

  const handleTimeChange = useCallback((timestamp: Date) => {
    setCurrentTime(timestamp)
  }, [])

  return (
    <AppLayout
      petName="Pixel"
      foodBalance={foodBalance}
      maxFood={1.0}
      messages={messages}
      onSendMessage={handleSendMessage}
      onTimeChange={handleTimeChange}
      currentTime={currentTime}
    >
      <WorldScene chunks={chunks} pet={pet} onVoxelClick={handleVoxelClick} />
      {/* Subtle connection status indicator */}
      <div className="fixed bottom-4 left-4 z-50 flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse'
          }`}
        />
        <span className="text-xs text-white/40">
          {isConnected ? 'Live' : PET_ID ? 'Reconnecting...' : 'Offline'}
        </span>
      </div>
    </AppLayout>
  )
}
