-- Pet body voxels table — stores the pet's current physical appearance (from define_self).
-- One row per pet, upserted each time the pet reshapes itself.
CREATE TABLE pet_body (
    pet_id UUID PRIMARY KEY REFERENCES pets(id) ON DELETE CASCADE,
    voxel_data JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
