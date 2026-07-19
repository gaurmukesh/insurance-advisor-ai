import contextvars

from sqlalchemy import select
from starlette.responses import JSONResponse

from app.db.postgres import AsyncSessionLocal
from app.mcp.tokens import resolve_advisor_id
from app.models.advisor import Advisor

# Set by MCPAuthMiddleware for the lifetime of one HTTP/SSE connection, read by
# app.mcp.rbac.require_role. Tool functions are plain callables registered with
# FastMCP -- unlike FastAPI routes there's no Depends() to inject the caller,
# so identity travels via contextvar instead of a function parameter.
current_advisor: contextvars.ContextVar[Advisor | None] = contextvars.ContextVar(
    "current_advisor", default=None
)


class MCPAuthMiddleware:
    """Authenticates every request to the mounted MCP transport (both the SSE
    connect and the POST /messages/ calls) with an opaque token minted by
    scripts/mint_mcp_token.py -- not the REST API's JWT. Opaque tokens are
    individually revocable (app.mcp.tokens.revoke_token) without invalidating
    every other advisor's token, which a JWT signing-key rotation would.
    Only covers the HTTP/SSE transport mounted in app.main -- the stdio
    transport (`python -m app.mcp.server`, used by Claude Desktop) has no HTTP
    layer to authenticate and is treated as a trusted local process, same as
    today."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        auth_header = headers.get(b"authorization", b"").decode()
        token = auth_header[len("Bearer "):] if auth_header.startswith("Bearer ") else None

        advisor = await self._authenticate(token) if token else None
        if advisor is None:
            response = JSONResponse({"detail": "Not authenticated"}, status_code=401)
            await response(scope, receive, send)
            return

        reset_token = current_advisor.set(advisor)
        try:
            await self.app(scope, receive, send)
        finally:
            current_advisor.reset(reset_token)

    @staticmethod
    async def _authenticate(token: str) -> Advisor | None:
        async with AsyncSessionLocal() as db:
            advisor_id = await resolve_advisor_id(db, token)
            if advisor_id is None:
                return None
            return (
                await db.execute(select(Advisor).where(Advisor.id == advisor_id))
            ).scalar_one_or_none()
