interface FloatingActionsProps {
  activePanel: 'none' | 'chat' | 'timeline' | 'schedule'
  onToggleChat: () => void
  onToggleTimeline: () => void
  onToggleSchedule: () => void
}

export default function FloatingActions({ activePanel, onToggleChat, onToggleTimeline, onToggleSchedule }: FloatingActionsProps) {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
      <button
        onClick={onToggleSchedule}
        className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110 ${
          activePanel === 'schedule'
            ? 'bg-white/30 backdrop-blur-md'
            : 'bg-black/50 backdrop-blur-md hover:bg-black/70'
        } border border-white/20`}
        aria-label="Toggle schedule"
      >
        {/* Calendar/list icon */}
        <svg
          className="w-5 h-5 text-white"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
          <line x1="8" y1="14" x2="8" y2="14.01" />
          <line x1="12" y1="14" x2="12" y2="14.01" />
          <line x1="16" y1="14" x2="16" y2="14.01" />
          <line x1="8" y1="18" x2="8" y2="18.01" />
          <line x1="12" y1="18" x2="12" y2="18.01" />
        </svg>
      </button>
      <button
        onClick={onToggleTimeline}
        className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110 ${
          activePanel === 'timeline'
            ? 'bg-white/30 backdrop-blur-md'
            : 'bg-black/50 backdrop-blur-md hover:bg-black/70'
        } border border-white/20`}
        aria-label="Toggle timeline"
      >
        <svg
          className="w-5 h-5 text-white"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      </button>
      <button
        onClick={onToggleChat}
        className={`w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 hover:scale-110 ${
          activePanel === 'chat'
            ? 'bg-white/30 backdrop-blur-md'
            : 'bg-black/50 backdrop-blur-md hover:bg-black/70'
        } border border-white/20`}
        aria-label="Toggle chat"
      >
        <svg
          className="w-5 h-5 text-white"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
        </svg>
      </button>
    </div>
  )
}
