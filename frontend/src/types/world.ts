export interface Voxel {
  x: number;
  y: number;
  z: number;
  r: number;
  g: number;
  b: number;
  a: number;
  metadata_id?: string;
}

export interface Chunk {
  chunk_x: number;
  chunk_y: number;
  chunk_z: number;
  voxels: Voxel[];
}

export interface PetEntity {
  position: { x: number; y: number; z: number };
  voxels: Voxel[];
}

export const CHUNK_SIZE = 16;
