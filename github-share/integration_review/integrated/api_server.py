"""HTTP entry point for MAINSU portfolio uploads."""
from starlette.applications import Starlette

from web_portfolios import routes

app = Starlette(routes=routes)
