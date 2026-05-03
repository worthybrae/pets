-- World snapshots (diffs for history/replay)
CREATE TABLE world_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    diff_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_world_snapshots_pet_id ON world_snapshots(pet_id);
CREATE INDEX idx_world_snapshots_created_at ON world_snapshots(pet_id, created_at DESC);
