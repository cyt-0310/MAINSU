"""HTTP entry point for MAINSU portfolio uploads."""
from starlette.applications import Starlette

from web_portfolios import routes

from web_interviews import routes as interview_routes
from starlette.responses import JSONResponse
from starlette.routing import Route

async def health(request):
    return JSONResponse({"status": "ok", "voice_interviews": True})

app = Starlette(routes=routes + interview_routes + [Route("/api/health", health)])
