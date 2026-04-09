-- ==========================================================================
-- PatentIQ — Initial Database Migration
-- PostgreSQL with pgvector extension (Neon-compatible)
-- ==========================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ==========================================================================
-- FIRMS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS firms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    clerk_org_id VARCHAR(255) UNIQUE NOT NULL,
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- USERS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clerk_user_id VARCHAR(255) UNIQUE NOT NULL,
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'attorney',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_users_firm ON users(firm_id);

-- ==========================================================================
-- PATENT FAMILIES
-- ==========================================================================
CREATE TABLE IF NOT EXISTS patent_families (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    family_name VARCHAR(500) NOT NULL,
    family_external_id VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_families_firm ON patent_families(firm_id);

-- ==========================================================================
-- PATENTS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS patents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    application_number VARCHAR(50) NOT NULL,
    patent_number VARCHAR(50),
    title TEXT NOT NULL,
    abstract TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    filing_date DATE,
    grant_date DATE,
    priority_date DATE,
    inventors JSONB DEFAULT '[]',
    assignee VARCHAR(500),
    classification JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    family_id UUID REFERENCES patent_families(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_firm_application UNIQUE(firm_id, application_number)
);

CREATE INDEX idx_patents_firm_status ON patents(firm_id, status);
CREATE INDEX idx_patents_application_number ON patents(application_number);
CREATE INDEX idx_patents_filing_date ON patents(filing_date);

-- Full-text search index
CREATE INDEX idx_patents_fts ON patents
    USING gin(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(abstract, '')));

-- Trigram index for fuzzy search
CREATE INDEX idx_patents_title_trgm ON patents USING gin(title gin_trgm_ops);

-- ==========================================================================
-- PATENT CLAIMS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS patent_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patent_id UUID NOT NULL REFERENCES patents(id) ON DELETE CASCADE,
    claim_number INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    is_independent BOOLEAN DEFAULT FALSE,
    depends_on INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_patent_claim_number UNIQUE(patent_id, claim_number)
);

CREATE INDEX idx_claims_patent ON patent_claims(patent_id);

-- ==========================================================================
-- OFFICE ACTIONS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS office_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patent_id UUID NOT NULL REFERENCES patents(id) ON DELETE CASCADE,
    action_type VARCHAR(100) NOT NULL,
    mailing_date DATE,
    response_deadline DATE,
    r2_file_key VARCHAR(500),
    extracted_text TEXT,
    rejections JSONB DEFAULT '[]',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_oa_patent_status ON office_actions(patent_id, status);
CREATE INDEX idx_oa_deadline ON office_actions(response_deadline);

-- ==========================================================================
-- OA RESPONSE DRAFTS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS oa_response_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    office_action_id UUID NOT NULL REFERENCES office_actions(id) ON DELETE CASCADE,
    created_by UUID NOT NULL REFERENCES users(id),
    draft_content TEXT NOT NULL,
    ai_model_used VARCHAR(100),
    status VARCHAR(50) DEFAULT 'draft',
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- PRIOR ART REFERENCES
-- ==========================================================================
CREATE TABLE IF NOT EXISTS prior_art_references (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patent_id UUID NOT NULL REFERENCES patents(id) ON DELETE CASCADE,
    reference_number VARCHAR(100) NOT NULL,
    reference_title TEXT,
    reference_abstract TEXT,
    reference_type VARCHAR(50) DEFAULT 'patent',
    relevance_score FLOAT,
    cited_by_examiner BOOLEAN DEFAULT FALSE,
    analysis_notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prior_art_patent ON prior_art_references(patent_id);

-- ==========================================================================
-- DRAFTS
-- ==========================================================================
CREATE TABLE IF NOT EXISTS drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patent_id UUID REFERENCES patents(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES users(id),
    firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT DEFAULT '',
    draft_type VARCHAR(50) DEFAULT 'application',
    ai_model_used VARCHAR(100),
    version INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_drafts_firm ON drafts(firm_id);

-- ==========================================================================
-- PATENT EMBEDDINGS (pgvector)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS patent_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patent_id UUID NOT NULL REFERENCES patents(id) ON DELETE CASCADE,
    chunk_index INTEGER DEFAULT 0,
    chunk_text TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_patent_embeddings_patent ON patent_embeddings(patent_id);

-- HNSW index for fast approximate nearest neighbor search
CREATE INDEX idx_patent_embeddings_hnsw ON patent_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ==========================================================================
-- CLAIM EMBEDDINGS (pgvector)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS claim_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_id UUID UNIQUE NOT NULL REFERENCES patent_claims(id) ON DELETE CASCADE,
    embedding vector(1024) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for claim-level semantic search
CREATE INDEX idx_claim_embeddings_hnsw ON claim_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ==========================================================================
-- ROW-LEVEL SECURITY (multi-tenant isolation)
-- ==========================================================================

-- Enable RLS on all tenant-scoped tables
ALTER TABLE patents ENABLE ROW LEVEL SECURITY;
ALTER TABLE patent_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE patent_families ENABLE ROW LEVEL SECURITY;
ALTER TABLE office_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE oa_response_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE prior_art_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE patent_embeddings ENABLE ROW LEVEL SECURITY;

-- RLS policies (filter by firm_id from session variable)
CREATE POLICY firm_isolation_patents ON patents
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY firm_isolation_families ON patent_families
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY firm_isolation_drafts ON drafts
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- For tables without direct firm_id, use JOIN-based policies
CREATE POLICY firm_isolation_claims ON patent_claims
    USING (patent_id IN (
        SELECT id FROM patents WHERE firm_id = current_setting('app.current_firm_id')::uuid
    ));

CREATE POLICY firm_isolation_oa ON office_actions
    USING (patent_id IN (
        SELECT id FROM patents WHERE firm_id = current_setting('app.current_firm_id')::uuid
    ));

CREATE POLICY firm_isolation_oa_drafts ON oa_response_drafts
    USING (office_action_id IN (
        SELECT oa.id FROM office_actions oa
        JOIN patents p ON oa.patent_id = p.id
        WHERE p.firm_id = current_setting('app.current_firm_id')::uuid
    ));

CREATE POLICY firm_isolation_prior_art ON prior_art_references
    USING (patent_id IN (
        SELECT id FROM patents WHERE firm_id = current_setting('app.current_firm_id')::uuid
    ));

CREATE POLICY firm_isolation_embeddings ON patent_embeddings
    USING (patent_id IN (
        SELECT id FROM patents WHERE firm_id = current_setting('app.current_firm_id')::uuid
    ));

-- ==========================================================================
-- UPDATED_AT TRIGGER
-- ==========================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_patents_updated_at
    BEFORE UPDATE ON patents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_drafts_updated_at
    BEFORE UPDATE ON drafts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_firms_updated_at
    BEFORE UPDATE ON firms
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
