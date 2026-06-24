-- Multi-tenancy: enforce advisor isolation at DB layer, not application layer.
-- Even if application code forgets to filter by advisor_id, Postgres blocks the query.

ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS advisor_isolation ON clients;
CREATE POLICY advisor_isolation ON clients
    USING (advisor_id = current_setting('app.current_advisor_id', true));

ALTER TABLE policies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS policy_isolation ON policies;
CREATE POLICY policy_isolation ON policies
    USING (client_id IN (
        SELECT id FROM clients
        WHERE advisor_id = current_setting('app.current_advisor_id', true)
    ));
