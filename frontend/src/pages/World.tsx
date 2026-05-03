import { useState, useCallback } from 'react'
import WorldScene from '../components/world/WorldScene'
import AppLayout from '../components/layout/AppLayout'
import type { ChatMessage } from '../components/ui/ChatPanel'
import { demoChunks, demoPet } from '../components/world/demoData'

const initialMessages: ChatMessage[] = [
  {
    id: '1',
    sender: 'Pixel',
    text: 'Hey there! I just finished building a little garden over by the east side. Want to come see?',
    timestamp: new Date(Date.now() - 1000 * 60 * 30),
  },
  {
    id: '2',
    sender: 'You',
    text: 'That sounds great! What did you plant?',
    timestamp: new Date(Date.now() - 1000 * 60 * 28),
  },
  {
    id: '3',
    sender: 'Pixel',
    text: 'Some voxel flowers and a tiny tree. I used the blue blocks you gave me for a little pond too!',
    timestamp: new Date(Date.now() - 1000 * 60 * 25),
  },
  {
    id: '4',
    sender: 'You',
    text: "That's adorable. Keep up the good work!",
    timestamp: new Date(Date.now() - 1000 * 60 * 20),
  },
  {
    id: '5',
    sender: 'Pixel',
    text: "Thanks! I'm going to explore the northern caves next. Maybe I'll find some crystals.",
    timestamp: new Date(Date.now() - 1000 * 60 * 15),
  },
]

export default function World() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages)
  const [currentTime, setCurrentTime] = useState<Date>(new Date())

  const handleVoxelClick = (metadataId: string) => {
    console.log('Artifact clicked:', metadataId)
  }

  const handleSendMessage = useCallback((text: string) => {
    const newMessage: ChatMessage = {
      id: Date.now().toString(),
      sender: 'You',
      text,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, newMessage])
  }, [])

  const handleTimeChange = useCallback((timestamp: Date) => {
    setCurrentTime(timestamp)
  }, [])

  return (
    <AppLayout
      petName="Pixel"
      foodBalance={0.65}
      maxFood={1.0}
      messages={messages}
      onSendMessage={handleSendMessage}
      onTimeChange={handleTimeChange}
      currentTime={currentTime}
    >
      <WorldScene
        chunks={demoChunks}
        pet={demoPet}
        onVoxelClick={handleVoxelClick}
      />
    </AppLayout>
  )
}
