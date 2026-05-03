-- World chunks table
CREATE TABLE world_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    chunk_x INTEGER NOT NULL,
    chunk_y INTEGER NOT NULL,
    chunk_z INTEGER NOT NULL,
    voxel_data JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for spatial lookups
CREATE INDEX idx_world_chunks_pet_id ON world_chunks(pet_id);
CREATE UNIQUE INDEX idx_world_chunks_position ON world_chunks(pet_id, chunk_x, chunk_y, chunk_z);
