-- RBAC: role column for MCP tool authorization (advisor | manager | admin).
-- Default 'advisor' preserves current behavior for every existing row.
ALTER TABLE advisors ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'advisor';
