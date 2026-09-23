import type { ColumnMesh } from './mesher'

export interface MeshRequest {
  type: 'mesh'
  key: string
  cx: number
  cz: number
  seed: string
  /** x, y, z, id quadruples for the column and its one-cell border. */
  edits: Int32Array
  version: number
}

export type WorkerRequest = MeshRequest

export interface MeshedResponse {
  type: 'meshed'
  key: string
  cx: number
  cz: number
  version: number
  /** The generated column without edits, for WorldStore.getBlock. */
  base: Uint8Array
  mesh: ColumnMesh
  ms: number
}

export interface ErrorResponse {
  type: 'error'
  key: string
  version: number
  message: string
}

export type WorkerResponse = MeshedResponse | ErrorResponse

export function meshTransfers(mesh: ColumnMesh): ArrayBuffer[] {
  return [mesh.opaque, mesh.cutout, mesh.translucent].flatMap((layer) => [
    layer.positions.buffer, layer.uvs.buffer, layer.colors.buffer, layer.glows.buffer, layer.indices.buffer,
  ] as ArrayBuffer[])
}
