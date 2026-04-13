"""FastAPI app: stateful handlers first, Prism proxy as catch-all fallthrough.

Registration order matters. FastAPI matches explicit routes before the
catch-all. So:
  1. Admin + UI routes (not part of eMASS surface)
  2. Stateful handlers for eMASS endpoints we intercept
  3. Catch-all /api/{path:path} → proxy to Prism (spec-conformant examples)
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import Response

from . import __version__
from .config import load_settings
from .handlers import artifacts, controls, poams, systems, test_results
from .middleware import FailureInjectionMiddleware
from .proxy import proxy_to_prism
from .routers import admin, ui
from .store import get_store


def create_app() -> FastAPI:
    settings = load_settings()
    get_store().seed(settings.seed_system_ids)

    app = FastAPI(
        title="emass-mock",
        version=__version__,
        description=(
            "Stateful test harness for eMASS integrations. Layers deterministic "
            "round-tripping and failure injection on top of MITRE's OpenAPI spec "
            "(served via Stoplight Prism). Not affiliated with DoD or MITRE."
        ),
    )
    app.add_middleware(FailureInjectionMiddleware)

    # Admin + UI first (bypass proxy, bypass auth).
    app.include_router(admin.router)
    app.include_router(ui.router)

    # Stateful eMASS handlers (the harness's value-add).
    app.include_router(systems.router)
    app.include_router(controls.router)
    app.include_router(test_results.router)
    app.include_router(artifacts.router)
    app.include_router(poams.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "version": __version__, "prism": settings.prism_url}

    # Fallthrough: anything under /api/ we didn't handle → Prism (if configured).
    @app.api_route(
        "/api/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        include_in_schema=False,
    )
    async def prism_fallthrough(path: str, request: Request) -> Response:
        return await proxy_to_prism(request)

    return app


app = create_app()
