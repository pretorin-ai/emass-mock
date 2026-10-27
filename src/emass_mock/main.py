"""FastAPI app: stateful handlers first, Prism proxy as catch-all fallthrough.

Registration order matters. FastAPI matches explicit routes before the
catch-all. So:
  1. Admin + UI routes (not part of eMASS surface)
  2. Stateful handlers for eMASS endpoints we intercept
  3. Catch-all /api/{path:path} → proxy to Prism (spec-conformant examples)

Every error the app itself raises is rendered in the eMASS envelope
(``{"meta": {"code": N, "errorMessage": "..."}}``), including auth failures
and malformed JSON, so a client never sees FastAPI's ``{"detail": ...}`` on
the eMASS surface.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .auth import AuthError
from .config import load_settings
from .envelope import error
from .handlers import (
    artifacts,
    baselines,
    controls,
    device_scan_results,
    milestones,
    poams,
    systems,
    test_connection,
    test_results,
)
from .middleware import FailureInjectionMiddleware
from .proxy import proxy_to_prism
from .routers import admin, ui
from .spec import MAX_ERRORS, spec_version
from .store import get_store
from .traffic import TrafficMiddleware

EMASS_ROUTERS = (
    test_connection.router,
    systems.router,
    controls.router,
    test_results.router,
    artifacts.router,
    poams.router,
    milestones.router,
    baselines.hardware_router,
    baselines.software_router,
    device_scan_results.router,
)

_HARNESS_PREFIXES = ("/_admin", "/ui", "/docs", "/redoc", "/openapi.json", "/health")


def create_app() -> FastAPI:
    settings = load_settings()
    get_store().seed(settings.seed_system_ids, settings.seed_assessment_procedures)

    app = FastAPI(
        title="emass-mock",
        version=__version__,
        description=(
            "Stateful test harness for eMASS integrations. Validates requests against "
            f"MITRE's OpenAPI spec (eMASS API {spec_version()}), layers deterministic "
            "round-tripping and failure injection on top, and falls through to "
            "Stoplight Prism for everything else. Not affiliated with DoD or MITRE."
        ),
    )
    app.add_middleware(FailureInjectionMiddleware)
    # Added last so it is outermost: it records injected failures too.
    app.add_middleware(TrafficMiddleware)
    app.mount(
        "/ui/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="ui-static",
    )

    @app.exception_handler(AuthError)
    async def _auth_error(request: Request, exc: AuthError) -> JSONResponse:
        return error(exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _malformed(request: Request, exc: RequestValidationError) -> JSONResponse:
        if request.url.path.startswith(_HARNESS_PREFIXES):
            # Invalid form input can contain UploadFile objects, exceptions,
            # or non-finite numbers that JSONResponse cannot serialize.
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {"loc": err["loc"], "msg": err["msg"], "type": err["type"]}
                        for err in exc.errors()[:MAX_ERRORS]
                    ]
                },
            )
        problems = "; ".join(
            "/".join(str(p) for p in err.get("loc", ())) + ": " + str(err.get("msg"))
            for err in exc.errors()[:MAX_ERRORS]
        )
        return error(400, f"Malformed request: {problems}")

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if request.url.path.startswith(_HARNESS_PREFIXES):
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return error(exc.status_code, str(exc.detail))

    # Admin + UI first (bypass proxy, bypass auth).
    app.include_router(admin.router)
    app.include_router(ui.router)

    # Stateful eMASS handlers (the harness's value-add). Kept on app.state so
    # the UI can tell which spec operations the mock answers itself.
    app.state.emass_routers = EMASS_ROUTERS
    for emass_router in EMASS_ROUTERS:
        app.include_router(emass_router)

    @app.get("/health", tags=["meta"])
    async def health() -> dict:
        return {
            "status": "ok",
            "version": __version__,
            "spec_version": spec_version(),
            "prism": settings.prism_url,
        }

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
