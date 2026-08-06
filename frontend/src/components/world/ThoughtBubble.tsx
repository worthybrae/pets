import { useState, useEffect, useRef } from 'react'
import { Html } from '@react-three/drei'

interface ThoughtBubbleProps {
  thought: string | null
  offset?: [number, number, number]
}

const DISPLAY_DURATION = 4000
const FADE_DURATION = 600

export default function ThoughtBubble({ thought, offset = [0, 8, 0] }: ThoughtBubbleProps) {
  const [visible, setVisible] = useState(false)
  const [displayText, setDisplayText] = useState<string | null>(null)
  const [fading, setFading] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fadeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!thought) return

    // Clear any existing timers
    if (timerRef.current) clearTimeout(timerRef.current)
    if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current)

    // Show new thought immediately
    setDisplayText(thought)
    setFading(false)
    setVisible(true)

    // Start fade after display duration
    timerRef.current = setTimeout(() => {
      setFading(true)
      fadeTimerRef.current = setTimeout(() => {
        setVisible(false)
        setDisplayText(null)
        setFading(false)
      }, FADE_DURATION)
    }, DISPLAY_DURATION)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (fadeTimerRef.current) clearTimeout(fadeTimerRef.current)
    }
  }, [thought])

  if (!visible || !displayText) return null

  return (
    <Html
      position={offset}
      center
      distanceFactor={20}
      style={{
        pointerEvents: 'none',
        transition: `opacity ${FADE_DURATION}ms ease-out`,
        opacity: fading ? 0 : 1,
      }}
    >
      <div
        style={{
          background: 'rgba(255, 255, 255, 0.95)',
          color: '#1a1a2e',
          padding: '6px 14px',
          borderRadius: '12px',
          fontSize: '13px',
          fontFamily: 'system-ui, -apple-system, sans-serif',
          fontWeight: 500,
          whiteSpace: 'nowrap',
          boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
          border: '1px solid rgba(0,0,0,0.08)',
          maxWidth: '240px',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}
      >
        {displayText}
      </div>
      {/* Small triangle pointer */}
      <div
        style={{
          width: 0,
          height: 0,
          borderLeft: '6px solid transparent',
          borderRight: '6px solid transparent',
          borderTop: '6px solid rgba(255, 255, 255, 0.95)',
          margin: '0 auto',
        }}
      />
    </Html>
  )
}
