-- Social graph
CREATE TABLE social_graph (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    neighbor_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    distance FLOAT NOT NULL DEFAULT 1.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_social_graph_pet_id ON social_graph(pet_id);
CREATE UNIQUE INDEX idx_social_graph_edge ON social_graph(pet_id, neighbor_id);

-- Visit log
CREATE TABLE visit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    visitor_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    host_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE INDEX idx_visit_log_visitor ON visit_log(visitor_id);
CREATE INDEX idx_visit_log_host ON visit_log(host_id);
