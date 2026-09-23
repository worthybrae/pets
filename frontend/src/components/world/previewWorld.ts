import type { PetEntity, Voxel } from '../../types/world'

type Color = readonly [number, number, number]

const petVoxels: Voxel[] = []
function petVoxel(x: number, y: number, z: number, color: Color) {
  petVoxels.push({ x, y, z, r: color[0], g: color[1], b: color[2], a: 255 })
}

const fur: Color = [242, 173, 148]
const lightFur: Color = [251, 204, 176]
const ear: Color = [215, 122, 129]

for (let x = -1; x <= 1; x++) {
  for (let z = -1; z <= 0; z++) {
    petVoxel(x, 0, z, fur)
    petVoxel(x, 1, z, fur)
  }
}
for (let x = -1; x <= 1; x++) {
  for (let z = 0; z <= 1; z++) {
    petVoxel(x, 2, z, lightFur)
    petVoxel(x, 3, z, lightFur)
  }
}
for (const x of [-1, 1]) {
  petVoxel(x, 4, 0, fur)
  petVoxel(x, 5, 0, ear)
  petVoxel(x, 0, 1, lightFur)
}
petVoxel(0, 1, -2, lightFur)

export const previewPet: PetEntity = {
  position: { x: 0, y: 1, z: 0 },
  voxels: petVoxels,
}
