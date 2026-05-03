-- Agendas table
CREATE TABLE agendas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pet_id UUID NOT NULL REFERENCES pets(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    plan JSONB NOT NULL DEFAULT '{"tasks": []}',
    current_task TEXT,
    food_allocated FLOAT NOT NULL DEFAULT 0.0,
    food_spent FLOAT NOT NULL DEFAULT 0.0
);

CREATE INDEX idx_agendas_pet_id ON agendas(pet_id);
CREATE UNIQUE INDEX idx_agendas_pet_date ON agendas(pet_id, date);
