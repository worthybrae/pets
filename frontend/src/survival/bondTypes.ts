/** Shapes of Bond in the survival API (backend/survival/bond_view.py and backend/api/bond.py). */

/** One line of the talk between the owner and Mimo. */
export interface ChatLine {
  id: number
  /** Server time it was written. */
  at: number
  who: 'owner' | 'mimo'
  text: string
}

/** How many more lines the owner may write this game hour and this real UTC day. */
export interface ChatLeft {
  hour: number
  day: number
}

/** The chat (backend/survival/talk.py chat_view): the newest lines, oldest first. */
export interface ChatView {
  lines: ChatLine[]
  /** True while Mimo has not answered the owner's last line yet. */
  waiting: boolean
  left: ChatLeft
}

/** The bond between Mimo and its owner (backend/survival/bond.py bond_view). */
export interface BondView {
  /** 0..100: care, hellos, talk and kept promises grow it; it fades while the owner stays away. */
  level: number
  feeling: 'shy' | 'friendly' | 'close' | 'devoted'
}

/** A request of the owner's that Mimo took up (backend/survival/requests.py request_view). */
export interface RequestView {
  goal: string
  title: string
  /** Server time it lapses; Bond's final fix wave (I5): null while it waits for its goal to open. */
  until: number | null
  /** The title of the goal a waiting promise waits for (I5; an older API sends none). */
  after?: string | null
  /** A shy "maybe", not a promise (m6). */
  maybe?: boolean
}

/** One message from Mimo (backend/survival/inbox.py). */
export interface InboxItem {
  id: number
  /** Server time. */
  at: number
  /** "ask", "report"; B3 adds "found", "danger" and "story"; Bond's final fix wave "hatched". */
  kind: string
  text: string
  /** A naming ask: {ask: "name", words, answer once named}; a care ask: {care, day (its UTC day), done once
   * that day's care was given (Bond's final fix wave, m14)}; a story: {day, last,
   * writer, and, for one Luna wrote and the rules later grew, lead, lead_last (Task 13's fix rounds), and
   * present for one written for an owner who was there (Bond follow-up, N3)}. */
  data: { ask?: string; words?: string; answer?: string; care?: string; day?: number | string; last?: number;
    writer?: string; lead?: number; lead_last?: number; done?: boolean; present?: boolean }
  read: boolean
}

/** The inbox in /api/mimo: how many messages are unread, and the newest unread few. */
export interface InboxView {
  unread: number
  newest: InboxItem[]
}

/** A story in Mimo's diary (backend/survival/diary.py diary_entries). */
export interface DiaryEntry {
  id: number
  /** Server time it was written. */
  at: number
  /** The game day it is about. */
  day: number
  /** Pre-flight 2: the last game day a story of a long absence tells (null or missing: `day` alone). */
  last?: number | null
  text: string
  writer: 'luna' | 'rules'
  read: boolean
  /** Bond follow-up (N3): written for an owner who was there that day, so it never pops up (an older API sends none). */
  present?: boolean
}

/** What /api/mimo adds for Bond while Mimo lives (an older API sends none of it). */
export interface BondFields {
  chat?: ChatView
  bond?: BondView
  inbox?: InboxView
  request?: RequestView | null
  /** B3: the newest story, shown first when the viewer opens while it is unread. */
  story?: DiaryEntry | null
}

/** A life's diary on its memorial (an older API sends none). */
export interface DiaryFields {
  diary?: DiaryEntry[]
}
