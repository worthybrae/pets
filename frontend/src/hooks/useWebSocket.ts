import { useEffect, useRef, useCallback, useState } from 'react'

export interface Position {
  x: number
  y: number
  z: number
}

export interface VoxelData {
  x: number
  y: number
  z: number
  r?: number
  g?: number
  b?: number
  a?: number
}

export interface VoxelUpdate {
  action: 'place' | 'remove'
  voxels: VoxelData[]
}

export interface ChatMessageWS {
  sender: string
  message: string
  timestamp: string
}

export interface ArtifactData {
  id: string
  type: string
  title: string
  content: string
  position: Position
}

export interface UseWebSocketOptions {
  petId: string | null
  onChatMessage?: (msg: ChatMessageWS) => void
  onVoxelUpdate?: (update: VoxelUpdate) => void
  onPetMoved?: (position: Position) => void
  onFoodUpdate?: (balance: number) => void
  onStatusChange?: (status: string) => void
  onArtifactPlaced?: (artifact: ArtifactData) => void
  onConnected?: () => void
}

interface UseWebSocketReturn {
  sendMessage: (text: string) => void
  sendPing: () => void
  isConnected: boolean
  disconnect: () => void
}

function getWebSocketUrl(petId: string): string {
  // Check for environment variable override
  const envUrl = import.meta.env.VITE_WS_URL
  if (envUrl) {
    return `${envUrl}/api/pets/${petId}/ws`
  }
  // Derive from window.location
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.hostname
  // Default backend port in development
  const port = import.meta.env.VITE_API_PORT || '8000'
  return `${protocol}//${host}:${port}/api/pets/${petId}/ws`
}

// Exponential backoff parameters
const INITIAL_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000
const BACKOFF_MULTIPLIER = 2

export function useWebSocket(options: UseWebSocketOptions): UseWebSocketReturn {
  const {
    petId,
    onChatMessage,
    onVoxelUpdate,
    onPetMoved,
    onFoodUpdate,
    onStatusChange,
    onArtifactPlaced,
    onConnected,
  } = options

  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY)
  const shouldReconnectRef = useRef(true)

  // Store callbacks in refs to avoid reconnecting on callback changes
  const callbacksRef = useRef({
    onChatMessage,
    onVoxelUpdate,
    onPetMoved,
    onFoodUpdate,
    onStatusChange,
    onArtifactPlaced,
    onConnected,
  })

  useEffect(() => {
    callbacksRef.current = {
      onChatMessage,
      onVoxelUpdate,
      onPetMoved,
      onFoodUpdate,
      onStatusChange,
      onArtifactPlaced,
      onConnected,
    }
  })

  const connect = useCallback(() => {
    if (!petId) return

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const url = getWebSocketUrl(petId)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setIsConnected(true)
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        const callbacks = callbacksRef.current

        switch (data.type) {
          case 'connected':
            callbacks.onConnected?.()
            break
          case 'chat':
            callbacks.onChatMessage?.({
              sender: data.sender,
              message: data.message,
              timestamp: data.timestamp,
            })
            break
          case 'voxel_update':
            callbacks.onVoxelUpdate?.({
              action: data.action,
              voxels: data.voxels,
            })
            break
          case 'pet_moved':
            callbacks.onPetMoved?.(data.position)
            break
          case 'food_update':
            callbacks.onFoodUpdate?.(data.balance)
            break
          case 'status_change':
            callbacks.onStatusChange?.(data.status)
            break
          case 'artifact_placed':
            callbacks.onArtifactPlaced?.(data.artifact)
            break
          case 'pong':
            // Keepalive response, no action needed
            break
          case 'error':
            console.warn('[WebSocket] Server error:', data.message)
            break
          default:
            console.debug('[WebSocket] Unknown message type:', data.type)
        }
      } catch (e) {
        console.error('[WebSocket] Failed to parse message:', e)
      }
    }

    ws.onclose = () => {
      setIsConnected(false)
      wsRef.current = null

      // Attempt reconnection with exponential backoff
      if (shouldReconnectRef.current) {
        const delay = reconnectDelayRef.current
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectDelayRef.current = Math.min(
            delay * BACKOFF_MULTIPLIER,
            MAX_RECONNECT_DELAY
          )
          connect()
        }, delay)
      }
    }

    ws.onerror = (error) => {
      console.error('[WebSocket] Connection error:', error)
      // onclose will fire after onerror, triggering reconnection
    }
  }, [petId])

  // Connect on mount / petId change
  useEffect(() => {
    shouldReconnectRef.current = true
    connect()

    return () => {
      shouldReconnectRef.current = false
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  const sendMessage = useCallback((text: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'chat', message: text }))
    } else {
      console.warn('[WebSocket] Cannot send message: not connected')
    }
  }, [])

  const sendPing = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'ping' }))
    }
  }, [])

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  return { sendMessage, sendPing, isConnected, disconnect }
}
