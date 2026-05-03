import { useState, useCallback } from 'react'
import { useWebSocket } from './useWebSocket'
import type { ChatMessageWS, VoxelUpdate, Position, ArtifactData } from './useWebSocket'
import type { ChatMessage } from '../components/ui/ChatPanel'

interface UseChatOptions {
  petId: string | null
  petName?: string
  onVoxelUpdate?: (update: VoxelUpdate) => void
  onPetMoved?: (position: Position) => void
  onFoodUpdate?: (balance: number) => void
  onStatusChange?: (status: string) => void
  onArtifactPlaced?: (artifact: ArtifactData) => void
}

interface UseChatReturn {
  messages: ChatMessage[]
  sendMessage: (text: string) => void
  isConnected: boolean
  clearMessages: () => void
}

let messageIdCounter = 0
function nextMessageId(): string {
  messageIdCounter += 1
  return `msg-${Date.now()}-${messageIdCounter}`
}

export function useChat(options: UseChatOptions): UseChatReturn {
  const {
    petId,
    petName = 'Pet',
    onVoxelUpdate,
    onPetMoved,
    onFoodUpdate,
    onStatusChange,
    onArtifactPlaced,
  } = options

  const [messages, setMessages] = useState<ChatMessage[]>([])

  const handleChatMessage = useCallback(
    (msg: ChatMessageWS) => {
      // Skip user echo messages since we optimistically add them locally
      if (msg.sender === 'user') return

      const newMessage: ChatMessage = {
        id: nextMessageId(),
        sender: msg.sender === 'pet' ? petName : msg.sender,
        text: msg.message,
        timestamp: new Date(msg.timestamp),
      }
      setMessages((prev) => [...prev, newMessage])
    },
    [petName]
  )

  const { sendMessage: wsSendMessage, isConnected } = useWebSocket({
    petId,
    onChatMessage: handleChatMessage,
    onVoxelUpdate,
    onPetMoved,
    onFoodUpdate,
    onStatusChange,
    onArtifactPlaced,
  })

  const sendMessage = useCallback(
    (text: string) => {
      if (!text.trim()) return

      // Optimistically add the user message to the local state
      const userMessage: ChatMessage = {
        id: nextMessageId(),
        sender: 'You',
        text: text.trim(),
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMessage])

      // Send via WebSocket
      wsSendMessage(text.trim())
    },
    [wsSendMessage]
  )

  const clearMessages = useCallback(() => {
    setMessages([])
  }, [])

  return { messages, sendMessage, isConnected, clearMessages }
}
