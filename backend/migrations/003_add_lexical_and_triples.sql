-- Add lexical tsvector column for pdf_chunks (computed at query time for immutability)
ALTER TABLE pdf_chunks
ADD COLUMN IF NOT EXISTS lexical_tsv tsvector;

-- Create index on lexical_tsv for fast full-text search
CREATE INDEX IF NOT EXISTS idx_pdf_chunks_lexical_tsv
    ON pdf_chunks USING GIN (lexical_tsv);

-- Create table for extracted triples
CREATE TABLE IF NOT EXISTS pdf_triples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pdf_metadata_id UUID NOT NULL REFERENCES pdf_metadata(id) ON DELETE CASCADE,
    chunk_id UUID NOT NULL REFERENCES pdf_chunks(id) ON DELETE CASCADE,
    page_num INT NOT NULL,
    chunk_index INT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL,
    triple_tsv tsvector
);

CREATE INDEX IF NOT EXISTS idx_pdf_triples_pdf
    ON pdf_triples(pdf_metadata_id);

CREATE INDEX IF NOT EXISTS idx_pdf_triples_tsv
    ON pdf_triples USING GIN (triple_tsv);

-- Trigger function to update lexical_tsv on pdf_chunks insert/update
CREATE OR REPLACE FUNCTION update_pdf_chunks_lexical_tsv()
RETURNS TRIGGER AS $$
BEGIN
    NEW.lexical_tsv := to_tsvector('english', COALESCE(NEW.chunk_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if it doesn't exist
DROP TRIGGER IF EXISTS trg_pdf_chunks_lexical_tsv ON pdf_chunks;
CREATE TRIGGER trg_pdf_chunks_lexical_tsv
BEFORE INSERT OR UPDATE ON pdf_chunks
FOR EACH ROW
EXECUTE FUNCTION update_pdf_chunks_lexical_tsv();

-- Trigger function to update triple_tsv on pdf_triples insert/update
CREATE OR REPLACE FUNCTION update_pdf_triples_triple_tsv()
RETURNS TRIGGER AS $$
BEGIN
    NEW.triple_tsv := to_tsvector('english', CONCAT_WS(' ', NEW.subject, NEW.predicate, NEW.object));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if it doesn't exist
DROP TRIGGER IF EXISTS trg_pdf_triples_triple_tsv ON pdf_triples;
CREATE TRIGGER trg_pdf_triples_triple_tsv
BEFORE INSERT OR UPDATE ON pdf_triples
FOR EACH ROW
EXECUTE FUNCTION update_pdf_triples_triple_tsv();
