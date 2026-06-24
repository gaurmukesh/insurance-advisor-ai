-- Prompt registry: versioned prompts swappable without code deploy
CREATE TABLE IF NOT EXISTS prompt_registry (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       VARCHAR(100) NOT NULL,
    version    INTEGER NOT NULL DEFAULT 1,
    content    TEXT NOT NULL,
    model      VARCHAR(50),
    is_active  BOOLEAN NOT NULL DEFAULT false,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (name, version)
);
CREATE INDEX IF NOT EXISTS idx_prompt_active ON prompt_registry(name, is_active);

-- Approval queue: human-in-the-loop gate before any AI action reaches a client
CREATE TABLE IF NOT EXISTS approval_queue (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id   VARCHAR(100),
    advisor_id  VARCHAR(100) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    payload     TEXT NOT NULL,
    status      VARCHAR(20) DEFAULT 'pending',
    reviewed_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_approval_advisor ON approval_queue(advisor_id, status);
