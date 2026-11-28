"""HTTP entry point for MAINSU portfolio uploads."""
import sys
from starlette.applications import Starlette

from web_portfolios import routes

from web_interviews import routes as interview_routes
from web_accounts import protect_workspaces, routes as account_routes
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
import web_postgres as pg

for stream in (sys.stdout, sys.stderr):
    if stream is not None and hasattr(stream, "reconfigure") and not stream.isatty():
        stream.reconfigure(encoding="utf-8", errors="backslashreplace")

async def health(request):
    return JSONResponse({"status": "ok", "voice_interviews": True,
                         "storage": "postgresql" if pg.enabled() else "local"})

app = Starlette(
    routes=routes + interview_routes + account_routes + [Route("/api/health", health)],
    middleware=[Middleware(BaseHTTPMiddleware, dispatch=protect_workspaces)],
)
