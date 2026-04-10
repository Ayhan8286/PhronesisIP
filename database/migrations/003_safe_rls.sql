-- ==========================================================================
-- PatentIQ Migration 003: Safe RLS Policies
-- Updates policies to use current_setting(..., true) to prevent 500 errors
-- if the session variable is missing.
-- ==========================================================================

-- 1. Drop existing policies
DROP POLICY IF EXISTS firm_isolation_patents ON patents;
DROP POLICY IF EXISTS firm_isolation_claims ON patent_claims;
DROP POLICY IF EXISTS firm_isolation_oa ON office_actions;
DROP POLICY IF EXISTS firm_isolation_oa_drafts ON oa_response_drafts;
DROP POLICY IF EXISTS firm_isolation_prior_art ON prior_art_references;
DROP POLICY IF EXISTS firm_isolation_embeddings ON patent_embeddings;
DROP POLICY IF EXISTS firm_isolation_claim_embeddings ON claim_embeddings;

-- 2. Create new "safe" policies (NULL if setting missing, comparison becomes false/unknown)
-- This prevents the "unrecognized configuration parameter" error.

CREATE POLICY firm_isolation_patents ON patents
    USING (firm_id = current_setting('app.current_firm_id', true)::uuid);

CREATE POLICY firm_isolation_claims ON patent_claims
    USING (firm_id = current_setting('app.current_firm_id', true)::uuid);

CREATE POLICY firm_isolation_oa ON office_actions
    USING (firm_id = current_setting('app.current_firm_id', true)::uuid);

CREATE POLICY firm_isolation_oa_drafts ON oa_response_drafts
    USING (firm_id = current_setting('app.current_firm_id', true)::uuid);

CREATE POLICY firm_isolation_prior_art ON prior_art_references
    USING (firm_id = current_setting('app.current_firm_id', true)::uuid);

CREATE POLICY firm_isolation_embeddings ON patent_embeddings
    USING (firm_id = current_setting('app.current_firm_id', true)::uuid);

CREATE POLICY firm_isolation_claim_embeddings ON claim_embeddings
    USING (firm_id = current_setting('app.current_firm_id', true)::uuid);
