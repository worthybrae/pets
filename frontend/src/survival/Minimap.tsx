import { useEffect, useMemo, useRef } from 'react'
import type { WorldStore } from '../engine/worldStore'
import {
  composeMap, MAP_BLOCKS, MAP_RADIUS, MAP_SCALE, mapMarks, mapOrigin, mapPatches, PATCH, PatchCache, PATCHES_PER_DRAW,
  seenPatches, travelHeading, type MapMark,
} from './overheadMap'
import type { Built, ExploredPatch, Landmark, MimoAction, Point } from './types'

const SIZE = MAP_BLOCKS * MAP_SCALE
const PET = '#f0845c'
const INK = '#243e3d'
const HOME = '#f5c46b'
const FARM = '#8a6a4f'
const SPROUT = '#9ed07a'
/** Patches this far past the map's edge stay cached, for a walk back. */
const KEEP_MARGIN = 4

function drawHome(context: CanvasRenderingContext2D, x: number, y: number, building: boolean): void {
  context.beginPath()
  context.moveTo(x - 10, y - 1)
  context.lineTo(x, y - 11)
  context.lineTo(x + 10, y - 1)
  context.lineTo(x + 7, y - 1)
  context.lineTo(x + 7, y + 9)
  context.lineTo(x - 7, y + 9)
  context.lineTo(x - 7, y - 1)
  context.closePath()
  context.fillStyle = building ? 'rgba(245, 196, 107, 0.55)' : HOME
  context.fill()
  context.lineWidth = 3
  context.strokeStyle = INK
  context.stroke()
  context.fillStyle = INK
  context.fillRect(x - 2, y + 3, 4, 6)  // the door
}

function drawFarm(context: CanvasRenderingContext2D, x: number, y: number, building: boolean): void {
  context.globalAlpha = building ? 0.6 : 1
  context.fillStyle = FARM
  context.fillRect(x - 8, y - 8, 16, 16)
  context.fillStyle = SPROUT
  for (const row of [-5, 0, 5]) context.fillRect(x - 6, y + row - 1, 12, 2)
  context.lineWidth = 2.5
  context.strokeStyle = INK
  context.strokeRect(x - 8, y - 8, 16, 16)
  context.globalAlpha = 1
}

function drawPet(context: CanvasRenderingContext2D, x: number, y: number, heading: number | null): void {
  if (heading !== null) {
    context.save()
    context.translate(x, y)
    context.rotate(heading)
    context.beginPath()
    context.moveTo(19, 0)
    context.lineTo(7, -7)
    context.lineTo(7, 7)
    context.closePath()
    context.fillStyle = PET
    context.fill()
    context.lineWidth = 2.5
    context.strokeStyle = INK
    context.stroke()
    context.restore()
  }
  context.beginPath()
  context.arc(x, y, 8, 0, Math.PI * 2)
  context.fillStyle = PET
  context.fill()
  context.lineWidth = 3.5
  context.strokeStyle = '#ffffff'
  context.stroke()
  context.beginPath()
  context.arc(x, y, 10, 0, Math.PI * 2)
  context.lineWidth = 1.5
  context.strokeStyle = INK
  context.stroke()
}

function drawMark(context: CanvasRenderingContext2D, mark: MapMark): void {
  const x = mark.px * MAP_SCALE, y = mark.py * MAP_SCALE
  if (mark.kind === 'home') drawHome(context, x, y, mark.building)
  else drawFarm(context, x, y, mark.building)
}

/**
 * A top-down map of the land 96 blocks each way around Mimo, north up: the terrain as the 3D
 * world has it (overheadMap.ts), greyed out where Mimo has never been, with home, the farm and Mimo
 * itself (an arrow shows the way it walks). It redraws when a new snapshot arrives, not every
 * frame, working out at most PATCHES_PER_DRAW new patches each time.
 */
export default function Minimap({ store, position, explored, structures, landmarks, action, name, onHide }: {
  store: WorldStore
  position: Point
  explored: readonly ExploredPatch[] | undefined
  structures: readonly Built[] | undefined
  landmarks: readonly Landmark[] | undefined
  action: MimoAction | null
  name: string
  onHide: () => void
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const buffer = useRef<HTMLCanvasElement | null>(null)
  const cache = useMemo(() => new PatchCache(store), [store])

  // Blocks Mimo places or digs redraw the patches they are in.
  useEffect(() => store.subscribe((columns) => cache.invalidate(columns)), [store, cache])

  useEffect(() => {
    const context = canvas.current?.getContext('2d')
    if (!context) return
    buffer.current ??= document.createElement('canvas')
    const offscreen = buffer.current
    offscreen.width = MAP_BLOCKS
    offscreen.height = MAP_BLOCKS
    const pixels = offscreen.getContext('2d')
    if (!pixels) return
    const origin = mapOrigin(position)
    cache.fill(mapPatches(origin), PATCHES_PER_DRAW)
    const low = [Math.floor(origin.x / PATCH) - KEEP_MARGIN, Math.floor(origin.z / PATCH) - KEEP_MARGIN]
    const high = [Math.floor((origin.x + MAP_BLOCKS) / PATCH) + KEEP_MARGIN, Math.floor((origin.z + MAP_BLOCKS) / PATCH) + KEEP_MARGIN]
    cache.prune((rx, rz) => rx >= low[0] && rx <= high[0] && rz >= low[1] && rz <= high[1])
    const seen = seenPatches(explored, position)
    const image = pixels.createImageData(MAP_BLOCKS, MAP_BLOCKS)
    composeMap(image.data, MAP_BLOCKS, origin, (rx, rz) => cache.get(rx, rz), (rx, rz) => seen.has(`${rx},${rz}`))
    pixels.putImageData(image, 0, 0)
    context.imageSmoothingEnabled = false
    context.clearRect(0, 0, SIZE, SIZE)
    context.drawImage(offscreen, 0, 0, SIZE, SIZE)
    for (const mark of mapMarks(structures, landmarks, origin)) drawMark(context, mark)
    const middle = (MAP_RADIUS + 0.5) * MAP_SCALE
    drawPet(context, middle, middle, travelHeading(action, position))
  }, [cache, position, explored, structures, landmarks, action])

  return (
    <div className="relative h-[110px] w-[110px] overflow-hidden rounded-2xl border-2 border-white/80 bg-[#b0beba] shadow-[0_14px_40px_rgba(57,95,91,0.18)] sm:h-[140px] sm:w-[140px]">
      <canvas ref={canvas} width={SIZE} height={SIZE} className="h-full w-full [image-rendering:pixelated]"
        role="img" aria-label={`Map of the land around ${name}. Grey land is where ${name} has not been yet.`} />
      <span aria-hidden="true" className="pointer-events-none absolute left-1/2 top-0.5 -translate-x-1/2 text-[10px] font-bold leading-none text-white [text-shadow:0_1px_2px_rgba(36,62,61,0.9)]">N</span>
      <button type="button" onClick={onHide} title="Hide the map (M)" aria-label="Hide the map"
        className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#243e3d]/60 text-xs leading-none text-white hover:bg-[#243e3d]/85">
        ×
      </button>
    </div>
  )
}
