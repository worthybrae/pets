import { useState, useCallback } from 'react'
import type { ReactNode } from 'react'
import FloatingActions from '../ui/FloatingActions'
import ChatPanel from '../ui/ChatPanel'
import type { ChatMessage } from '../ui/ChatPanel'
import TimelinePanel from '../ui/TimelinePanel'
import SchedulePanel from '../ui/SchedulePanel'
import type { AgendaTask } from '../ui/SchedulePanel'

type PanelState = 'none' | 'chat' | 'timeline' | 'schedule'

interface AppLayoutProps {
  petName: string
  messages: ChatMessage[]
  onSendMessage: (text: string) => void
  onTimeChange: (timestamp: Date) => void
  currentTime: Date
  scheduleTasks: AgendaTask[]
  nextTaskTime: number | null
  children: ReactNode
}

export default function AppLayout({
  petName,
  messages,
  onSendMessage,
  onTimeChange,
  currentTime,
  scheduleTasks,
  nextTaskTime,
  children,
}: AppLayoutProps) {
  const [activePanel, setActivePanel] = useState<PanelState>('none')

  const handleToggleChat = useCallback(() => {
    setActivePanel((prev) => (prev === 'chat' ? 'none' : 'chat'))
  }, [])

  const handleToggleTimeline = useCallback(() => {
    setActivePanel((prev) => (prev === 'timeline' ? 'none' : 'timeline'))
  }, [])

  const handleToggleSchedule = useCallback(() => {
    setActivePanel((prev) => (prev === 'schedule' ? 'none' : 'schedule'))
  }, [])

  return (
    <div className="relative w-screen h-screen overflow-hidden">
      {/* World canvas fills entire viewport */}
      <div className="fixed inset-0 z-0">
        {children}
      </div>

      {/* Panels */}
      <ChatPanel
        messages={messages}
        onSend={onSendMessage}
        petName={petName}
        isOpen={activePanel === 'chat'}
      />
      <TimelinePanel
        onTimeChange={onTimeChange}
        currentTime={currentTime}
        isOpen={activePanel === 'timeline'}
      />
      <SchedulePanel
        tasks={scheduleTasks}
        isOpen={activePanel === 'schedule'}
        nextTaskTime={nextTaskTime}
        petName={petName}
      />

      {/* Floating action buttons */}
      <FloatingActions
        activePanel={activePanel}
        onToggleChat={handleToggleChat}
        onToggleTimeline={handleToggleTimeline}
        onToggleSchedule={handleToggleSchedule}
      />
    </div>
  )
}
