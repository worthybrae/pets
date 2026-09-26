import { useState } from 'react'
import TalkPanel from './TalkPanel'
import { newestReply, talkLabel } from './talk'
import type { AliveResponse } from './types'

/** Bond, under the care buttons: talking with Mimo. */
export default function BondBar({ state, onChanged }: { state: AliveResponse; onChanged: () => Promise<void> }) {
  const [talking, setTalking] = useState(false)
  // Replies that were already there when the page opened count as seen.
  const [seen, setSeen] = useState(() => newestReply(state.chat))
  const name = state.life.name
  const openTalk = () => {
    setSeen(newestReply(state.chat))
    setTalking(true)
  }
  const closeTalk = () => {
    setSeen(newestReply(state.chat))
    setTalking(false)
  }
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <button type="button" onClick={openTalk}
        className="rounded-xl border border-[#bfd5cd] px-3 py-2 text-sm font-medium text-[#315e58] hover:bg-white">
        {talking ? 'Talk' : talkLabel(state.chat, seen)}
      </button>
      {talking && <TalkPanel name={name} chat={state.chat} onSent={onChanged} onClose={closeTalk} />}
    </div>
  )
}
