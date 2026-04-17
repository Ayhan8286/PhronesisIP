-- ==========================================================================
-- PhronesisIP — Legal Knowledge Base Migration
-- Adds strict RAG infrastructure: legal sources + chunked embeddings
-- ==========================================================================

-- ==========================================================================
-- LEGAL SOURCES (metadata for uploaded legal documents)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS legal_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,  -- NULL = global source
    jurisdiction VARCHAR(50) NOT NULL DEFAULT 'USPTO',
        -- 'USPTO' | 'EPO' | 'JPO' | 'CNIPA' | 'IP_AUSTRALIA' | 'WIPO' | 'firm'
    doc_type VARCHAR(50) NOT NULL DEFAULT 'guideline',
        -- 'statute' | 'rule' | 'guideline' | 'firm_policy' | 'case_law'
    title VARCHAR(500) NOT NULL,
    version VARCHAR(50),            -- e.g. "2024.01", "Rev. 10"
    r2_key VARCHAR(500),            -- original PDF stored in Cloudflare R2
    is_active BOOLEAN DEFAULT TRUE, -- only active sources used in generation
    chunk_count INTEGER DEFAULT 0,  -- denormalized for quick display
    source_updated_at TIMESTAMPTZ,  -- when the actual legal document was last updated
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_legal_sources_firm ON legal_sources(firm_id);
CREATE INDEX idx_legal_sources_jurisdiction ON legal_sources(jurisdiction);
CREATE INDEX idx_legal_sources_active ON legal_sources(is_active) WHERE is_active = TRUE;

-- ==========================================================================
-- LEGAL SOURCE CHUNKS (chunked text + vector embeddings)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS legal_source_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES legal_sources(id) ON DELETE CASCADE,
    firm_id UUID REFERENCES firms(id) ON DELETE CASCADE,  -- denormalized for RLS
    chunk_text TEXT NOT NULL,
    chunk_index INTEGER DEFAULT 0,
    section VARCHAR(200),           -- e.g. "35 U.S.C. § 112", "MPEP § 2111.01"
    page_number INTEGER,
    embedding vector(1024) NOT NULL, -- Voyage AI voyage-law-2
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_lsc_source ON legal_source_chunks(source_id);
CREATE INDEX idx_lsc_firm ON legal_source_chunks(firm_id);

-- HNSW index for fast approximate nearest neighbor search
-- Matches the existing patent_embeddings index configuration
CREATE INDEX idx_lsc_embedding_hnsw ON legal_source_chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ==========================================================================
-- ROW-LEVEL SECURITY
-- ==========================================================================

-- Legal sources: global sources (firm_id IS NULL) are visible to all,
-- firm-specific sources are only visible to that firm
ALTER TABLE legal_sources ENABLE ROW LEVEL SECURITY;

CREATE POLICY legal_sources_isolation ON legal_sources
    USING (
        firm_id IS NULL
        OR firm_id = current_setting('app.current_firm_id', true)::uuid
    );

ALTER TABLE legal_source_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY legal_source_chunks_isolation ON legal_source_chunks
    USING (
        firm_id IS NULL
        OR firm_id = current_setting('app.current_firm_id', true)::uuid
    );

-- ==========================================================================
-- UPDATED_AT TRIGGER (reuses existing function)
-- ==========================================================================
CREATE TRIGGER update_legal_sources_updated_at
    BEFORE UPDATE ON legal_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
