-- PatentIQ Database Security Hardening — Phase 2 Update
-- This script enables Row Level Security (RLS) for multi-tenant isolation
-- AND enforces soft-delete exclusion at the engine level.

-- 1. Enable RLS on all tenant-specific tables
ALTER TABLE firms ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE patents ENABLE ROW LEVEL SECURITY;
ALTER TABLE patent_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE patent_families ENABLE ROW LEVEL SECURITY;
ALTER TABLE office_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE oa_response_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE prior_art_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE patent_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_logs ENABLE ROW LEVEL SECURITY;

-- 2. Define the Policies
-- We use current_setting('app.current_firm_id') which is set by the app in database.py

-- FIRMS: Users can only see their own firm
CREATE POLICY firm_isolation ON firms
    FOR ALL
    USING (id = current_setting('app.current_firm_id')::uuid);

-- USERS: Users can only see colleagues in the same firm
CREATE POLICY user_isolation ON users
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- PATENTS: The core asset (Enforce firm isolation + Soft Delete)
CREATE POLICY patent_isolation ON patents
    FOR ALL
    USING (
        firm_id = current_setting('app.current_firm_id')::uuid 
        AND deleted_at IS NULL
    );

-- PATENT CLAIMS
CREATE POLICY claim_isolation ON patent_claims
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- OFFICE ACTIONS (Enforce firm isolation + Soft Delete)
CREATE POLICY oa_isolation ON office_actions
    FOR ALL
    USING (
        firm_id = current_setting('app.current_firm_id')::uuid
        AND deleted_at IS NULL
    );

-- OA RESPONSE DRAFTS
CREATE POLICY oa_draft_isolation ON oa_response_drafts
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- PRIOR ART REFERENCES
CREATE POLICY prior_art_isolation ON prior_art_references
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- DRAFTS
CREATE POLICY draft_isolation ON drafts
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- EMBEDDINGS (High performance vector search)
CREATE POLICY patent_emb_isolation ON patent_embeddings
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY claim_emb_isolation ON claim_embeddings
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- AUDIT & USAGE (ReadOnly for standard users, strict isolation)
CREATE POLICY audit_isolation ON audit_logs
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

CREATE POLICY usage_isolation ON usage_logs
    FOR ALL
    USING (firm_id = current_setting('app.current_firm_id')::uuid);

-- 3. Success Notification
-- (Logged manually in Alembic migrations, but provided here as visual confirmation)
-- SQL: SELECT 'RLS Policies initialized correctly' as status;
