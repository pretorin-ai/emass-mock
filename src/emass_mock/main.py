"""FastAPI application wiring."""

from __future__ import annotations

from fastapi import FastAPI

from . import __version__
from .config import load_settings
from .middleware import FailureInjectionMiddleware
from .routers import admin, artifacts, controls, poams, systems, test_results, ui
from .store import get_store


def create_app() -> FastAPI:
    settings = load_settings()
    get_store().seed(settings.seed_system_ids)

    app = FastAPI(
        title="emass-mock",
        version=__version__,
        description=(
            "Open-source mock of the eMASS REST API. Not affiliated with DoD or MITRE. "
            "Use for local dev, CI, and partner integration testing only."
        ),
    )
    app.add_middleware(FailureInjectionMiddleware)

    app.include_router(systems.router)
    app.include_router(controls.router)
    app.include_router(test_results.router)
    app.include_router(artifacts.router)
    app.include_router(poams.router)
    app.include_router(admin.router)
    app.include_router(ui.router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {"status": "ok", "version": __version__}

    return app


app = create_app()
