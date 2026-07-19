-- Opaque, revocable tokens for the MCP HTTP/SSE transport, replacing the
-- self-signed JWTs create_mcp_token() used to issue. Only the raw random
-- token is ever handed to a client; the DB stores its SHA-256 hash, so a
-- single compromised token can be revoked (revoked_at) without invalidating
-- every other advisor's token, unlike rotating SECRET_KEY.
CREATE TABLE IF NOT EXISTS mcp_tokens (
    id VARCHAR PRIMARY KEY,
    advisor_id VARCHAR NOT NULL REFERENCES advisors(id),
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mcp_tokens_hash ON mcp_tokens(token_hash);
CREATE INDEX IF NOT EXISTS idx_mcp_tokens_advisor ON mcp_tokens(advisor_id);
