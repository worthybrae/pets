import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { seasonSky } from './seasons'
import { dayness, rgbToHex, skyColor } from './sky'
import type { SkyView } from './types'
import { flashAt, flashSky, weatherFog, weatherSky } from './weather'

/**
 * Lights that follow the game clock: sky and fog color and a sun and ambient light that dim at
 * night. Terrain dims through BlockWorld's daylight callback instead, because the terrain
 * materials ignore scene lights. W2: the season and the weather (`sky`) tint the sky and the fog, fog
 * closes in (`fog`: the fog's near and far in clear weather), and a lightning strike lifts the light for a
 * moment at replay time `now`.
 */
export default function DayNight({ seconds, sky = null, now, fog }: {
  seconds: () => number
  sky?: SkyView | null
  now?: () => number
  fog?: [number, number]
}) {
  const ambient = useRef<THREE.AmbientLight>(null)
  const sun = useRef<THREE.DirectionalLight>(null)
  const color = useRef(new THREE.Color())

  useFrame((state) => {
    const time = seconds()
    const light = dayness(time)
    const flash = now ? flashAt(sky?.strikes, now()) : 1
    const tinted = weatherSky(seasonSky(skyColor(time), sky?.season, light), sky?.weather)
    color.current.set(rgbToHex(flashSky(tinted, flash)))
    if (state.scene.background instanceof THREE.Color) state.scene.background.copy(color.current)
    if (state.scene.fog instanceof THREE.Fog) {
      state.scene.fog.color.copy(color.current)
      if (fog) [state.scene.fog.near, state.scene.fog.far] = weatherFog(fog[0], fog[1], sky?.weather)
    }
    if (ambient.current) ambient.current.intensity = (0.3 + 0.5 * light) * flash
    if (sun.current) sun.current.intensity = (0.25 + 1.45 * light) * flash
  })

  return (
    <>
      <ambientLight ref={ambient} intensity={0.8} />
      <directionalLight ref={sun} position={[12, 24, 16]} intensity={1.7} />
      <directionalLight position={[-10, 8, -12]} intensity={0.35} color="#d5eaff" />
    </>
  )
}

/** A soft warm light above the pet that fades in after dusk, so the pet stays visible at night. */
export function PetGlow({ seconds }: { seconds: () => number }) {
  const light = useRef<THREE.PointLight>(null)
  useFrame(() => {
    if (light.current) light.current.intensity = 2.2 * (1 - dayness(seconds()))
  })
  // Local to the pet's group, which is scaled by 0.31: this sits about 2.5 blocks above the pet.
  return <pointLight ref={light} position={[0.5, 8, 0.5]} intensity={0} distance={9} decay={1} color="#ffd9a8" />
}
