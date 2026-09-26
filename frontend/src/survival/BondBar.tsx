import { useEffect, useRef, useState } from 'react'
import { HEARTS, heartMeter, inboxLabel, noteVisit, promiseLine, visitDue } from './bond'
import DiaryPanel from './DiaryPanel'
import InboxPanel from './InboxPanel'
import StoryPanel from './StoryPanel'
import {
  awayLongEnough, gameDayMs, loadNotify, markStoryRead, newestUnread, notifyPlan, notifyShown, openedStoryId, saveNotify,
  storyOnOpen,
} from './story'
import TalkPanel from './TalkPanel'
import { newestReply, talkLabel } from './talk'
import type { AliveResponse } from './types'

const browserStorage = () => window.localStorage
const canNotify = () => typeof Notification !== 'undefined'

/** Bond, under the care buttons: the heart meter, talking with Mimo, its inbox and (B3) its diary; the
 * newest story first while it is unread, and opt-in browser notifications. Bond's final fix wave (I4): only the
 * story waiting when the viewer opened (or when the tab came back after a game day hidden) pops up; one written
 * while the owner watches goes quietly into the inbox and the diary. */
export default function BondBar({ state, onChanged }: { state: AliveResponse; onChanged: () => Promise<void> }) {
  const [talking, setTalking] = useState(false)
  const [reading, setReading] = useState(false)
  // Replies that were already there when the page opened count as seen.
  const [seen, setSeen] = useState(() => newestReply(state.chat))
  const lastVisit = useRef<number | null>(null)
  const [diaryOpen, setDiaryOpen] = useState(false)
  const [closedStory, setClosedStory] = useState(0)
  // The story waiting when the viewer opened: the only one that pops up (I4).
  const [openedStory, setOpenedStory] = useState(() => openedStoryId(state.story))
  const latestStory = useRef(state.story)
  const hiddenAt = useRef<number | null>(null)
  const dayMs = gameDayMs(state.clock)
  const [notify, setNotify] = useState(() => loadNotify(browserStorage))
  // Messages already there when the viewer opens never notify.
  const notified = useRef(newestUnread(state.inbox))
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

  // Back after a game day hidden: the story waiting then pops up, as when the viewer opens (I4).
  useEffect(() => {
    latestStory.current = state.story
  }, [state.story])
  useEffect(() => {
    const seen = () => {
      if (document.visibilityState === 'hidden') {
        hiddenAt.current = Date.now()
        return
      }
      if (awayLongEnough(hiddenAt.current, Date.now(), dayMs)) setOpenedStory(openedStoryId(latestStory.current))
      hiddenAt.current = null
    }
    document.addEventListener('visibilitychange', seen)
    return () => document.removeEventListener('visibilitychange', seen)
  }, [dayMs])

  // Opted in: one browser notification for the messages that came since the last one told.
  const { inbox } = state
  useEffect(() => {
    const plan = notifyPlan(inbox, notified.current, name, document.visibilityState === 'visible')
    if (!plan) return
    notified.current = plan.upTo
    if (notify && canNotify() && Notification.permission === 'granted') {
      new Notification(plan.title, { body: plan.body, tag: 'mimo-inbox' })
    }
  }, [inbox, notify, name])

  const chooseNotify = async (on: boolean) => {
    if (on && canNotify() && Notification.permission === 'default') await Notification.requestPermission()
    const granted = on && canNotify() && Notification.permission === 'granted'
    setNotify(granted)
    saveNotify(browserStorage, granted)
  }
  const story = storyOnOpen(openedStory, state.story, closedStory)
  const closeStory = (id: number) => {
    setClosedStory(id)
    markStoryRead(id).then(onChanged).catch(() => undefined)
  }
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
        <button type="button" onClick={() => setDiaryOpen(true)} className={button}>Diary</button>
      </div>
      {promise && <p className="mt-1 truncate text-xs text-[#54726e]">{promise}</p>}
      {talking && <TalkPanel name={name} chat={state.chat} onSent={onChanged} onClose={closeTalk} />}
      {reading && <InboxPanel name={name} notify={notifyShown(notify, canNotify() ? Notification.permission : undefined)}
        canNotify={canNotify()} onNotify={(on) => { void chooseNotify(on) }}
        onChanged={onChanged} onClose={() => setReading(false)} />}
      {story && <StoryPanel name={name} story={story} onClose={() => closeStory(story.id)}
        onDiary={() => { closeStory(story.id); setDiaryOpen(true) }} />}
      {diaryOpen && <DiaryPanel name={name} onClose={() => setDiaryOpen(false)} />}
    </div>
  )
}
