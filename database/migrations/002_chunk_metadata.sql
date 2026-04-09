-- ==========================================================================
-- PatentIQ — Migration 002: Chunk Metadata for RAG Pipeline
-- Adds page_number, section_type, firm_id to patent_embeddings
-- ==========================================================================

-- Add metadata columns to patent_embeddings
-- These match the exact schema from the RAG architecture:
-- [patent_id, chunk_text, vector(1024), page_number, section_type, firm_id]

ALTER TABLE patent_embeddings
    ADD COLUMN IF NOT EXISTS page_number INTEGER,
    ADD COLUMN IF NOT EXISTS section_type VARCHAR(50) DEFAULT 'description',
    ADD COLUMN IF NOT EXISTS firm_id UUID REFERENCES firms(id);

-- Backfill firm_id from patent's firm_id for existing rows
UPDATE patent_embeddings pe
SET firm_id = p.firm_id
FROM patents p
WHERE pe.patent_id = p.id
AND pe.firm_id IS NULL;

-- Index on firm_id for fast tenant-scoped vector search
-- This eliminates the JOIN to patents table during search
CREATE INDEX IF NOT EXISTS idx_patent_embeddings_firm
    ON patent_embeddings(firm_id);

-- Composite index: firm + section for filtered searches
CREATE INDEX IF NOT EXISTS idx_patent_embeddings_firm_section
    ON patent_embeddings(firm_id, section_type);
