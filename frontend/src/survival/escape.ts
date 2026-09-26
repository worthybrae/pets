import { useEffect, useRef } from 'react'

/** Whether a key closes a panel: Escape (Bond's final fix wave: every panel, not only the talk). */
export function closesOnEscape(key: string): boolean {
  return key === 'Escape'
}

/** Escape closes the panel while it is open: one window listener while mounted, for every panel (Journal,
 * Memories, Workshop, Inbox, Diary, the story, Talk, and Blocks & crafting). */
export function useEscape(onClose: () => void): void {
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  }, [onClose])
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!event.repeat && closesOnEscape(event.key)) close.current()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
