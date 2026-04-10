-- ==========================================================================
-- PatentIQ Migration 002: Soft Delete & Firm Context Sync
-- Adds missing columns expected by the application models
-- ==========================================================================

-- 1. Add Soft Delete support
ALTER TABLE patents ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_patents_deleted_at ON patents(deleted_at);

ALTER TABLE office_actions ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE office_actions ADD COLUMN IF NOT EXISTS firm_id UUID REFERENCES firms(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS idx_office_actions_deleted_at ON office_actions(deleted_at);
CREATE INDEX IF NOT EXISTS idx_office_actions_firm_id ON office_actions(firm_id);

-- 2. Add firm_id to child tables for better multi-tenancy performance and RLS
-- We make them nullable first to avoid errors if there's data, but the models expect NOT NULL.
-- In a dev environment, we can usually just add them or backfill.

ALTER TABLE patent_claims ADD COLUMN IF NOT EXISTS firm_id UUID REFERENCES firms(id) ON DELETE CASCADE;
ALTER TABLE patent_embeddings ADD COLUMN IF NOT EXISTS firm_id UUID REFERENCES firms(id) ON DELETE CASCADE;
ALTER TABLE claim_embeddings ADD COLUMN IF NOT EXISTS firm_id UUID REFERENCES firms(id) ON DELETE CASCADE;
ALTER TABLE oa_response_drafts ADD COLUMN IF NOT EXISTS firm_id UUID REFERENCES firms(id) ON DELETE CASCADE;
ALTER TABLE prior_art_references ADD COLUMN IF NOT EXISTS firm_id UUID REFERENCES firms(id) ON DELETE CASCADE;

-- 3. Add chunk metadata to embeddings
ALTER TABLE patent_embeddings ADD COLUMN IF NOT EXISTS page_number INTEGER;
ALTER TABLE patent_embeddings ADD COLUMN IF NOT EXISTS section_type VARCHAR(50) DEFAULT 'description';

-- 4. Backfill firm_id from parent tables where possible
UPDATE office_actions SET firm_id = p.firm_id FROM patents p WHERE office_actions.patent_id = p.id AND office_actions.firm_id IS NULL;
UPDATE patent_claims SET firm_id = p.firm_id FROM patents p WHERE patent_claims.patent_id = p.id AND patent_claims.firm_id IS NULL;
UPDATE patent_embeddings SET firm_id = p.firm_id FROM patents p WHERE patent_embeddings.patent_id = p.id AND patent_embeddings.firm_id IS NULL;
UPDATE claim_embeddings SET firm_id = pc.firm_id FROM patent_claims pc WHERE claim_embeddings.claim_id = pc.id AND claim_embeddings.firm_id IS NULL;
UPDATE oa_response_drafts SET firm_id = oa.firm_id FROM office_actions oa WHERE oa_response_drafts.office_action_id = oa.id AND oa_response_drafts.firm_id IS NULL;
UPDATE prior_art_references SET firm_id = p.firm_id FROM patents p WHERE prior_art_references.patent_id = p.id AND prior_art_references.firm_id IS NULL;

-- 5. Update RLS Policies to use direct firm_id columns
-- Drop old joining policies
DROP POLICY IF EXISTS firm_isolation_claims ON patent_claims;
DROP POLICY IF EXISTS firm_isolation_oa ON office_actions;
DROP POLICY IF EXISTS firm_isolation_oa_drafts ON oa_response_drafts;
DROP POLICY IF EXISTS firm_isolation_prior_art ON prior_art_references;
DROP POLICY IF EXISTS firm_isolation_embeddings ON patent_embeddings;

-- Create new simplified policies
CREATE POLICY firm_isolation_claims ON patent_claims
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY firm_isolation_oa ON office_actions
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY firm_isolation_oa_drafts ON oa_response_drafts
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY firm_isolation_prior_art ON prior_art_references
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY firm_isolation_embeddings ON patent_embeddings
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

ALTER TABLE claim_embeddings ENABLE ROW LEVEL SECURITY;
CREATE POLICY firm_isolation_claim_embeddings ON claim_embeddings
    USING (firm_id = current_setting('app.current_firm_id')::uuid);
