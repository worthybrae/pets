import { useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import { blockDef, blockId } from '../engine/blocks'
import { leafPuffs, puffBits } from './effects'
import type { LeafDecay } from './types'

const BITS = 6
const MAX_PUFFS = 8
const [LEAF_R, LEAF_G, LEAF_B] = blockDef(blockId('leaves')).color
const LEAF_COLOR = new THREE.Color().setRGB(LEAF_R / 255, LEAF_G / 255, LEAF_B / 255, THREE.SRGBColorSpace)

/** A small puff of leaf bits where each decaying leaf goes, drawn at `now` (the replay time). */
export default function LeafPuffs({ decays, now }: { decays: LeafDecay[]; now: () => number }) {
  const bits = useRef<THREE.InstancedMesh>(null)
  const scratch = useRef<THREE.Object3D | null>(null)

  useFrame(() => {
    const mesh = bits.current
    if (!mesh) return
    const puffs = leafPuffs(decays, now()).slice(-MAX_PUFFS)
    const dummy = (scratch.current ??= new THREE.Object3D())
    let shown = 0
    for (const puff of puffs) {
      const { offsets, scale } = puffBits(BITS, puff.age)
      for (const offset of offsets) {
        dummy.position.set(puff.cell.x + 0.5 + offset.x, puff.cell.y + 0.5 + offset.y, puff.cell.z + 0.5 + offset.z)
        dummy.scale.setScalar(scale)
        dummy.updateMatrix()
        mesh.setMatrixAt(shown++, dummy.matrix)
      }
    }
    mesh.count = shown
    mesh.visible = shown > 0
    mesh.instanceMatrix.needsUpdate = true
  })

  return (
    <instancedMesh ref={bits} args={[undefined, undefined, BITS * MAX_PUFFS]} visible={false} frustumCulled={false}>
      <boxGeometry args={[0.14, 0.14, 0.14]} />
      <meshLambertMaterial color={LEAF_COLOR} />
    </instancedMesh>
  )
}
