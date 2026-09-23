import { buildAtlas } from './atlas'
import { buildPaddedVolume, ColumnCache } from './columnVolume'
import { meshColumn } from './mesher'
import { meshTransfers, type WorkerRequest, type WorkerResponse } from './workerProtocol'

// The DOM lib types `self` as Window; describe the two worker members this file uses.
const scope = self as unknown as {
  onmessage: ((event: MessageEvent<WorkerRequest>) => void) | null
  postMessage: (message: WorkerResponse, transfer: Transferable[]) => void
}

const { faceTiles } = buildAtlas()
let cache: ColumnCache | null = null

scope.onmessage = (event) => {
  const request = event.data
  const started = performance.now()
  try {
    if (!cache || cache.seed !== request.seed) cache = new ColumnCache(request.seed)
    const columns = cache
    const volume = buildPaddedVolume(request.cx, request.cz, (cx, cz) => columns.get(cx, cz), request.edits)
    const mesh = meshColumn({ cx: request.cx, cz: request.cz, volume, faceTiles })
    const base = columns.get(request.cx, request.cz).slice()
    scope.postMessage({
      type: 'meshed', key: request.key, cx: request.cx, cz: request.cz, version: request.version,
      base, mesh, ms: performance.now() - started,
    }, [base.buffer as ArrayBuffer, ...meshTransfers(mesh)])
  } catch (error) {
    scope.postMessage({
      type: 'error', key: request.key, version: request.version,
      message: error instanceof Error ? error.message : String(error),
    }, [])
  }
}
