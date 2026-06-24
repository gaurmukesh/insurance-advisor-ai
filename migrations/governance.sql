-- AI Audit Log: immutable record of every AI decision
CREATE TABLE IF NOT EXISTS ai_audit_log (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_name  VARCHAR(100) NOT NULL,
    client_id   VARCHAR(100),
    advisor_id  VARCHAR(100),
    input_hash  VARCHAR(64),        -- SHA-256 of scrubbed input
    model       VARCHAR(50),
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    latency_ms  INTEGER,
    outcome     VARCHAR(20) DEFAULT 'success',
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_audit_trace  ON ai_audit_log(trace_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_client ON ai_audit_log(client_id);
