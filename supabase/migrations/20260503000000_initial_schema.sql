-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Pets table
CREATE TABLE IF NOT EXISTS pets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    seed_curiosity TEXT NOT NULL,
    food_balance FLOAT NOT NULL DEFAULT 100.0,
    status TEXT NOT NULL DEFAULT 'idle',
    position_x FLOAT NOT NULL DEFAULT 0.0,
    position_y FLOAT NOT NULL DEFAULT 0.0,
    position_z FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pets_owner_id ON pets(owner_id);

-- World chunks table
CREATE TABLE IF NOT EXISTS world_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    chunk_x INTEGER NOT NULL,
    chunk_y INTEGER NOT NULL,
    chunk_z INTEGER NOT NULL,
    voxel_data JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_world_chunks_pet_id ON world_chunks(pet_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_world_chunks_position ON world_chunks(pet_id, chunk_x, chunk_y, chunk_z);

-- Raw events (Tier 1 memory)
CREATE TABLE IF NOT EXISTS raw_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_events_pet_id ON raw_events(pet_id);
CREATE INDEX IF NOT EXISTS idx_raw_events_created_at ON raw_events(pet_id, created_at DESC);

-- Digested notes (Tier 2 memory)
CREATE TABLE IF NOT EXISTS digested_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digested_notes_pet_id ON digested_notes(pet_id);

-- Knowledge base (Tier 3 memory)
CREATE TABLE IF NOT EXISTS knowledge_base (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_knowledge_base_pet_id ON knowledge_base(pet_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_knowledge_base_key ON knowledge_base(pet_id, key);

-- Artifacts table
CREATE TABLE IF NOT EXISTS artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    s3_key TEXT,
    world_x FLOAT NOT NULL DEFAULT 0.0,
    world_y FLOAT NOT NULL DEFAULT 0.0,
    world_z FLOAT NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_artifacts_pet_id ON artifacts(pet_id);

-- Agendas table
CREATE TABLE IF NOT EXISTS agendas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    plan JSONB NOT NULL DEFAULT '{"tasks": []}',
    current_task TEXT,
    food_allocated FLOAT NOT NULL DEFAULT 0.0,
    food_spent FLOAT NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_agendas_pet_id ON agendas(pet_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_agendas_pet_date ON agendas(pet_id, date);

-- Social graph
CREATE TABLE IF NOT EXISTS social_graph (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    neighbor_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    distance FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_social_graph_pet_id ON social_graph(pet_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_social_graph_edge ON social_graph(pet_id, neighbor_id);

-- Visit log
CREATE TABLE IF NOT EXISTS visit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    visitor_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    host_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_visit_log_visitor ON visit_log(visitor_id);
CREATE INDEX IF NOT EXISTS idx_visit_log_host ON visit_log(host_id);

-- World snapshots (diffs for history/replay)
CREATE TABLE IF NOT EXISTS world_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    diff_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_world_snapshots_pet_id ON world_snapshots(pet_id);
CREATE INDEX IF NOT EXISTS idx_world_snapshots_created_at ON world_snapshots(pet_id, created_at DESC);

-- Vector similarity search function for the memory system
CREATE OR REPLACE FUNCTION match_memories(
    query_embedding vector(1536),
    match_threshold float,
    match_count int,
    p_pet_id uuid,
    p_table_name text
)
RETURNS TABLE (id uuid, content text, similarity float)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_table_name = 'raw_events' THEN
        RETURN QUERY
        SELECT re.id, re.content,
            1 - (re.embedding <=> query_embedding)::float AS similarity
        FROM raw_events re
        WHERE re.pet_id = p_pet_id
            AND re.embedding IS NOT NULL
            AND 1 - (re.embedding <=> query_embedding) > match_threshold
        ORDER BY re.embedding <=> query_embedding
        LIMIT match_count;
    ELSIF p_table_name = 'digested_notes' THEN
        RETURN QUERY
        SELECT dn.id, dn.content,
            1 - (dn.embedding <=> query_embedding)::float AS similarity
        FROM digested_notes dn
        WHERE dn.pet_id = p_pet_id
            AND dn.embedding IS NOT NULL
            AND 1 - (dn.embedding <=> query_embedding) > match_threshold
        ORDER BY dn.embedding <=> query_embedding
        LIMIT match_count;
    ELSIF p_table_name = 'knowledge_base' THEN
        RETURN QUERY
        SELECT kb.id, kb.content,
            1 - (kb.embedding <=> query_embedding)::float AS similarity
        FROM knowledge_base kb
        WHERE kb.pet_id = p_pet_id
            AND kb.embedding IS NOT NULL
            AND 1 - (kb.embedding <=> query_embedding) > match_threshold
        ORDER BY kb.embedding <=> query_embedding
        LIMIT match_count;
    END IF;
END;
$$;
