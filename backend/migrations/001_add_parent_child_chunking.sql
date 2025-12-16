-- Migration: Add parent-child chunking columns to pdf_chunks
-- Version: 001
-- Date: 2024-12-16
-- Description: Implements hierarchical chunking with parent-child relationships

-- Create the chunk_type enum if it doesn't exist
DO $$ BEGIN
    CREATE TYPE chunktype AS ENUM ('PARENT', 'CHILD');
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Add new columns to pdf_chunks table
ALTER TABLE pdf_chunks
ADD COLUMN IF NOT EXISTS parent_chunk_id UUID REFERENCES pdf_chunks(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS chunk_type chunktype NOT NULL DEFAULT 'CHILD',
ADD COLUMN IF NOT EXISTS token_count INTEGER;

-- Create index for parent-child lookups
CREATE INDEX IF NOT EXISTS idx_pdf_chunks_parent_chunk_id 
ON pdf_chunks(parent_chunk_id);

-- Create index for chunk_type filtering (for embedding only CHILD chunks)
CREATE INDEX IF NOT EXISTS idx_pdf_chunks_chunk_type 
ON pdf_chunks(chunk_type);

-- Composite index for efficient embedding queries
CREATE INDEX IF NOT EXISTS idx_pdf_chunks_embed_child 
ON pdf_chunks(pdf_metadata_id, chunk_type, embedded) 
WHERE chunk_type = 'CHILD';

-- Update existing chunks to be CHILD type (they were the search targets)
-- Note: Existing chunks don't have parents, so parent_chunk_id stays NULL
UPDATE pdf_chunks SET chunk_type = 'CHILD' WHERE chunk_type IS NULL;

-- Add comment for documentation
COMMENT ON COLUMN pdf_chunks.parent_chunk_id IS 'Links child chunks to their parent chunk for hierarchical context';
COMMENT ON COLUMN pdf_chunks.chunk_type IS 'PARENT chunks provide context, CHILD chunks are embedded for vector search';
COMMENT ON COLUMN pdf_chunks.token_count IS 'Accurate token count using embedding model tokenizer';

-- Verify migration
SELECT 
    'pdf_chunks columns:' as info,
    column_name, 
    data_type 
FROM information_schema.columns 
WHERE table_name = 'pdf_chunks'
ORDER BY ordinal_position;
