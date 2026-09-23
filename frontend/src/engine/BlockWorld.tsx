import { useEffect, useRef, useState } from 'react'
import { useFrame, useThree } from '@react-three/fiber'
import * as THREE from 'three'
import { ColumnRenderer, type WorldStats } from './columnRenderer'
import type { WorldStore } from './worldStore'

export interface ViewStats extends WorldStats {
  fps: number
  drawCalls: number
}

interface BlockWorldProps {
  store: WorldStore
  centerX: number
  centerZ: number
  viewDistance: number
  /** Called every frame for the terrain brightness (1 day, 0.35 night). Omit for full daylight. */
  daylight?: () => number
  onStats?: (stats: ViewStats) => void
  onError?: (message: string) => void
}

export default function BlockWorld({ store, centerX, centerZ, viewDistance, daylight, onStats, onError }: BlockWorldProps) {
  const { gl } = useThree()
  const [group] = useState(() => new THREE.Group())
  const renderer = useRef<ColumnRenderer | null>(null)
  const onErrorRef = useRef(onError)
  const statsClock = useRef({ elapsed: 0, frames: 0 })

  useEffect(() => { onErrorRef.current = onError }, [onError])

  useEffect(() => {
    const next = new ColumnRenderer(store, group, (message) => onErrorRef.current?.(message))
    renderer.current = next
    return () => {
      next.dispose()
      renderer.current = null
    }
  }, [store, group])

  useEffect(() => {
    renderer.current?.setView(centerX, centerZ, viewDistance)
  }, [store, centerX, centerZ, viewDistance])

  useEffect(() => {
    const canvas = gl.domElement
    const restore = () => renderer.current?.restoreGpuResources()
    canvas.addEventListener('webglcontextrestored', restore)
    return () => canvas.removeEventListener('webglcontextrestored', restore)
  }, [gl])

  useFrame((_, delta) => {
    const current = renderer.current
    if (!current) return
    current.setDaylight(daylight ? daylight() : 1)
    current.tick(delta)
    if (!onStats) return
    const clock = statsClock.current
    clock.elapsed += delta
    clock.frames += 1
    if (clock.elapsed < 0.5) return
    onStats({ ...current.stats(), fps: Math.round(clock.frames / clock.elapsed), drawCalls: gl.info.render.calls })
    clock.elapsed = 0
    clock.frames = 0
  })

  return <primitive object={group} />
}
