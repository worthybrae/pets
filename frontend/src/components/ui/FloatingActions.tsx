interface FloatingActionsProps {
  activePanel: 'none' | 'chat' | 'timeline'
  onToggleChat: () => void
  onToggleTimeline: () => void
}

export default function FloatingActions({ activePanel, onToggleChat, onToggleTimeline }: FloatingActionsProps) {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
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
