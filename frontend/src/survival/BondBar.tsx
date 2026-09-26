import { useEffect, useRef, useState } from 'react'
import { HEARTS, heartMeter, inboxLabel, noteVisit, promiseLine, visitDue } from './bond'
import InboxPanel from './InboxPanel'
import TalkPanel from './TalkPanel'
import { newestReply, talkLabel } from './talk'
import type { AliveResponse } from './types'

/** Bond, under the care buttons: the heart meter, talking with Mimo and its inbox. */
export default function BondBar({ state, onChanged }: { state: AliveResponse; onChanged: () => Promise<void> }) {
  const [talking, setTalking] = useState(false)
  const [reading, setReading] = useState(false)
  // Replies that were already there when the page opened count as seen.
  const [seen, setSeen] = useState(() => newestReply(state.chat))
  const lastVisit = useRef<number | null>(null)
  const name = state.life.name
  const lifeId = state.life.id

  // The owner is here: told when the viewer opens, then every ten minutes while the tab shows.
  useEffect(() => {
    lastVisit.current = null
    const tell = () => {
      const now = Date.now()
      if (!visitDue(lastVisit.current, now, document.visibilityState === 'visible')) return
      lastVisit.current = now
      noteVisit().catch(() => { lastVisit.current = null })
    }
    tell()
    const timer = window.setInterval(tell, 60_000)
    document.addEventListener('visibilitychange', tell)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', tell)
    }
  }, [lifeId])

  const openTalk = () => {
    setSeen(newestReply(state.chat))
    setTalking(true)
  }
  const closeTalk = () => {
    setSeen(newestReply(state.chat))
    setTalking(false)
  }
  const meter = heartMeter(state.bond)
  const promise = promiseLine(state.request, state.server_time)
  const button = 'rounded-xl border border-[#bfd5cd] px-3 py-2 text-sm font-medium text-[#315e58] hover:bg-white'
  return (
    <div className="mt-2">
      <div className="flex flex-wrap items-center gap-2">
        {meter && (
          <span className="inline-flex items-center gap-0.5 pr-1 text-base leading-none" title={meter.label} role="img" aria-label={meter.label}>
            {Array.from({ length: HEARTS }, (_, index) => (
              <span key={index} className={index < meter.full ? 'text-[#c76e5c]' : 'text-[#dccbc6]'}>♥</span>
            ))}
          </span>
        )}
        <button type="button" onClick={openTalk} className={button}>{talking ? 'Talk' : talkLabel(state.chat, seen)}</button>
        <button type="button" onClick={() => setReading(true)} className={button}>{inboxLabel(state.inbox)}</button>
      </div>
      {promise && <p className="mt-1 truncate text-xs text-[#54726e]">{promise}</p>}
      {talking && <TalkPanel name={name} chat={state.chat} onSent={onChanged} onClose={closeTalk} />}
      {reading && <InboxPanel name={name} onChanged={onChanged} onClose={() => setReading(false)} />}
    </div>
  )
}
