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

/** What /api/mimo adds for Bond while Mimo lives (an older API sends none of it). */
export interface BondFields {
  chat?: ChatView
}
