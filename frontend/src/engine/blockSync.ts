import type { PlacedBlock } from './worldStore'

export interface BlocksPage {
  seq: number
  changes: PlacedBlock[]
  more: boolean
}

type FetchPage = (since: number) => Promise<BlocksPage>
type ApplyChanges = (changes: PlacedBlock[], reset: boolean) => void

/** Pages /api/mimo/blocks into the store. Errors reach the caller; the next poll retries. */
export class BlockSync {
  seq = 0
  private readonly fetchPage: FetchPage
  private readonly apply: ApplyChanges
  private running = false
  private pendingReset = false

  constructor(fetchPage: FetchPage, apply: ApplyChanges) {
    this.fetchPage = fetchPage
    this.apply = apply
  }

  async syncTo(serverSeq: number): Promise<boolean> {
    if (this.running || serverSeq === this.seq) return false
    this.running = true
    try {
      if (serverSeq < this.seq) {
        // The server database was reset. Start over and drop local server edits.
        this.seq = 0
        this.pendingReset = true
      }
      let more = true
      while (more) {
        const page = await this.fetchPage(this.seq)
        this.apply(page.changes, this.pendingReset)
        this.pendingReset = false
        this.seq = page.seq
        more = page.more
      }
      return true
    } finally {
      this.running = false
    }
  }
}
