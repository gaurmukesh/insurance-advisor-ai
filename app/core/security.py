from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
# mcp-remote (Claude Desktop's bridge to the deployed /mcp/sse endpoint) has no
# interactive re-login flow, unlike the REST session token above -- a 7-day
# expiry would silently break the Claude Desktop config every week.
MCP_TOKEN_EXPIRE_DAYS = 365


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def create_access_token(advisor_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": advisor_id, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_mcp_token(advisor_id: str) -> str:
    """Long-lived token for the mcp-remote SSE bridge. decode_token() reads
    the same "sub" claim, so MCPAuthMiddleware needs no special-casing --
    this only differs from create_access_token() in expiry length."""
    expire = datetime.now(timezone.utc) + timedelta(days=MCP_TOKEN_EXPIRE_DAYS)
    payload = {"sub": advisor_id, "exp": expire, "scope": "mcp"}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """Returns the advisor_id encoded in the token. Raises jwt.PyJWTError on failure."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    return payload["sub"]
