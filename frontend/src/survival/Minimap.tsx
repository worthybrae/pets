import { useEffect, useMemo, useRef } from 'react'
import type { WorldStore } from '../engine/worldStore'
import {
  composeMap, MAP_BLOCKS, MAP_RADIUS, MAP_SCALE, mapMarks, mapOrigin, mapPatches, PATCH, PatchCache, PATCHES_PER_DRAW,
  seenPatches, spreadMarks, travelHeading, type MapMark,
} from './overheadMap'
import { creatureDots } from './creatures'
import type { Built, Creature, ExploredPatch, Landmark, MimoAction, Point } from './types'

const SIZE = MAP_BLOCKS * MAP_SCALE
const PET = '#f0845c'
const INK = '#243e3d'
const HOME = '#f5c46b'
const FARM = '#8a6a4f'
const SPROUT = '#9ed07a'
const ANIMAL = '#fff4de'
const FISH = '#6fb8d8'
/** Patches this far past the map's edge stay cached, for a walk back. */
const KEEP_MARGIN = 4
/** The map's width on screen before it is laid out (desktop), in CSS pixels. */
const SHOWN = 140
/** Glyph sizes in CSS pixels, whatever size the map is shown at. */
const HOUSE = 7  // half the house's width at the eaves
const FIELD = 6  // half the farm's width
const DOT = 3.5  // Mimo's radius
const DOT_AT_HOME = 2.5  // inside its house glyph, so the house shows round it
const ARROW = 9  // how far ahead of Mimo its arrow points
/** Farms closer than this (CSS pixels) to a house glyph are drawn beside it instead. */
const GAP = 15

/** The house outline, `u` canvas pixels to a CSS pixel, centred on (x, y). */
function housePath(context: CanvasRenderingContext2D, x: number, y: number, u: number): void {
  const eave = HOUSE * u, wall = 0.7 * HOUSE * u
  context.beginPath()
  context.moveTo(x - eave, y - 0.5 * u)
  context.lineTo(x, y - 7 * u)
  context.lineTo(x + eave, y - 0.5 * u)
  context.lineTo(x + wall, y - 0.5 * u)
  context.lineTo(x + wall, y + 6 * u)
  context.lineTo(x - wall, y + 6 * u)
  context.lineTo(x - wall, y - 0.5 * u)
  context.closePath()
}

function drawHome(context: CanvasRenderingContext2D, x: number, y: number, building: boolean, u: number): void {
  housePath(context, x, y, u)
  context.fillStyle = building ? 'rgba(245, 196, 107, 0.6)' : HOME
  context.fill()
  context.lineWidth = 1.2 * u
  context.strokeStyle = INK
  context.stroke()
  context.fillStyle = INK
  context.fillRect(x - 1.2 * u, y + 2 * u, 2.4 * u, 4 * u)  // the door
}

/** The house's outline again, over Mimo's dot when it is at home, so both show. */
function ringHome(context: CanvasRenderingContext2D, x: number, y: number, u: number): void {
  housePath(context, x, y, u)
  context.lineWidth = 1.5 * u
  context.strokeStyle = INK
  context.stroke()
}

function drawFarm(context: CanvasRenderingContext2D, x: number, y: number, building: boolean, u: number): void {
  const half = FIELD * u
  context.globalAlpha = building ? 0.6 : 1
  context.fillStyle = FARM
  context.fillRect(x - half, y - half, 2 * half, 2 * half)
  context.fillStyle = SPROUT
  for (const row of [-3.5, 0, 3.5]) context.fillRect(x - half + u, y + (row - 0.6) * u, 2 * half - 2 * u, 1.2 * u)
  context.lineWidth = 1.1 * u
  context.strokeStyle = INK
  context.strokeRect(x - half, y - half, 2 * half, 2 * half)
  context.globalAlpha = 1
}

function drawPet(context: CanvasRenderingContext2D, x: number, y: number, heading: number | null, u: number,
  dot: number): void {
  if (heading !== null) {
    context.save()
    context.translate(x, y)
    context.rotate(heading)
    context.beginPath()
    context.moveTo(ARROW * u, 0)
    context.lineTo((dot + 0.5) * u, -3.2 * u)
    context.lineTo((dot + 0.5) * u, 3.2 * u)
    context.closePath()
    context.fillStyle = PET
    context.fill()
    context.lineWidth = 1 * u
    context.strokeStyle = INK
    context.stroke()
    context.restore()
  }
  context.beginPath()
  context.arc(x, y, dot * u, 0, Math.PI * 2)
  context.fillStyle = PET
  context.fill()
  context.lineWidth = 1.3 * u
  context.strokeStyle = '#ffffff'
  context.stroke()
  context.beginPath()
  context.arc(x, y, (dot + 1) * u, 0, Math.PI * 2)
  context.lineWidth = 0.7 * u
  context.strokeStyle = INK
  context.stroke()
}

function drawMark(context: CanvasRenderingContext2D, mark: MapMark, u: number): void {
  const x = mark.px * MAP_SCALE, y = mark.py * MAP_SCALE
  if (mark.kind === 'home') drawHome(context, x, y, mark.building, u)
  else drawFarm(context, x, y, mark.building, u)
}

/** A creature (L1): a small cream dot, blue for a fish, about 4 CSS pixels across at any size the map shows. */
function drawCreature(context: CanvasRenderingContext2D, x: number, y: number, fish: boolean): void {
  const u = SIZE / (context.canvas.clientWidth || 140)  // canvas pixels to a CSS pixel
  context.beginPath()
  context.arc(x, y, 2 * u, 0, Math.PI * 2)
  context.fillStyle = fish ? FISH : ANIMAL
  context.fill()
  context.lineWidth = 0.8 * u
  context.strokeStyle = INK
  context.stroke()
}

/**
 * A top-down map of the land 96 blocks each way around Mimo, north up: the terrain as the 3D
 * world has it (overheadMap.ts), greyed out where Mimo has never been, with home, the farm and Mimo
 * itself (an arrow shows the way it walks; at home the house's outline is drawn over it). Glyphs
 * keep the same size on screen whether the map shows at 140 or 110 px. It redraws when a new
 * snapshot arrives, not every frame, working out at most PATCHES_PER_DRAW new patches each time.
 */
export default function Minimap({ store, position, explored, structures, landmarks, creatures, action, name, onHide }: {
  store: WorldStore
  position: Point
  explored: readonly ExploredPatch[] | undefined
  structures: readonly Built[] | undefined
  landmarks: readonly Landmark[] | undefined
  /** The creatures near Mimo (L1), drawn as small dots. */
  creatures?: readonly Creature[]
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
    // Glyphs keep their size on screen: `u` canvas pixels make one CSS pixel at the shown size.
    const u = SIZE / (canvas.current?.clientWidth || SHOWN)
    const marks = spreadMarks(mapMarks(structures, landmarks, origin), (GAP * u) / MAP_SCALE)
    for (const mark of marks) if (mark.kind === 'farm') drawMark(context, mark, u)
    for (const mark of marks) if (mark.kind === 'home') drawMark(context, mark, u)
    for (const dot of creatureDots(creatures, origin)) drawCreature(context, dot.px * MAP_SCALE, dot.py * MAP_SCALE, dot.fish)
    const middle = (MAP_RADIUS + 0.5) * MAP_SCALE
    // At home Mimo's dot shrinks and the house's outline is drawn over it, so both show.
    const homes = marks.filter((mark) => mark.kind === 'home'
      && Math.hypot(mark.px * MAP_SCALE - middle, mark.py * MAP_SCALE - middle) < HOUSE * u)
    drawPet(context, middle, middle, travelHeading(action, position), u, homes.length ? DOT_AT_HOME : DOT)
    for (const home of homes) ringHome(context, home.px * MAP_SCALE, home.py * MAP_SCALE, u)
  }, [cache, position, explored, structures, landmarks, creatures, action])

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
