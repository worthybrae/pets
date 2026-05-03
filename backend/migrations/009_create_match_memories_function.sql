-- Vector similarity search function for the memory system.
-- Searches across any of the three memory tables using cosine distance.
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
        SELECT
            re.id,
            re.content,
            1 - (re.embedding <=> query_embedding)::float AS similarity
        FROM raw_events re
        WHERE re.pet_id = p_pet_id
            AND re.embedding IS NOT NULL
            AND 1 - (re.embedding <=> query_embedding) > match_threshold
        ORDER BY re.embedding <=> query_embedding
        LIMIT match_count;

    ELSIF p_table_name = 'digested_notes' THEN
        RETURN QUERY
        SELECT
            dn.id,
            dn.content,
            1 - (dn.embedding <=> query_embedding)::float AS similarity
        FROM digested_notes dn
        WHERE dn.pet_id = p_pet_id
            AND dn.embedding IS NOT NULL
            AND 1 - (dn.embedding <=> query_embedding) > match_threshold
        ORDER BY dn.embedding <=> query_embedding
        LIMIT match_count;

    ELSIF p_table_name = 'knowledge_base' THEN
        RETURN QUERY
        SELECT
            kb.id,
            kb.content,
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
