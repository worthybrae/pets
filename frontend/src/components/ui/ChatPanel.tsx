import { useState, useRef, useEffect } from 'react'

export interface ChatMessage {
  id: string
  sender: string
  text: string
  timestamp: Date
}

interface ChatPanelProps {
  messages: ChatMessage[]
  onSend: (text: string) => void
  petName: string
  isOpen: boolean
}

export default function ChatPanel({ messages, onSend, petName, isOpen }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim()) {
      onSend(input.trim())
      setInput('')
    }
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div
      className={`fixed top-0 right-0 bottom-0 z-40 flex flex-col backdrop-blur-md bg-black/60 border-l border-white/10 transition-transform duration-300 ease-in-out w-full sm:w-[380px] ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <h2 className="text-white font-medium">Chat with {petName}</h2>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id} className="flex flex-col gap-1">
            <div className="flex items-baseline gap-2">
              <span className={`text-sm font-medium ${
                msg.sender === petName ? 'text-green-400' : 'text-blue-400'
              }`}>
                {msg.sender}
              </span>
              <span className="text-white/40 text-xs">
                {formatTime(msg.timestamp)}
              </span>
            </div>
            <p className="text-white/90 text-sm leading-relaxed">
              {msg.text}
            </p>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-4 py-3 border-t border-white/10">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Say something..."
            className="flex-1 bg-white/10 border border-white/20 rounded-lg px-3 py-2 text-white text-sm placeholder-white/40 focus:outline-none focus:border-white/40 transition-colors"
          />
          <button
            type="submit"
            disabled={!input.trim()}
            className="px-4 py-2 bg-white/20 hover:bg-white/30 disabled:opacity-40 disabled:hover:bg-white/20 rounded-lg text-white text-sm font-medium transition-colors"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  )
}
