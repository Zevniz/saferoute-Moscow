"""FastAPI application factory for SafeRoute Moscow."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.core.observability import configure_logging, request_logging_middleware

APP_DIR = Path(__file__).resolve().parents[1]
INDEX_FILE = APP_DIR / "index.html"


def create_app() -> FastAPI:
    """Create and configure the SafeRoute API app."""

    settings = get_settings()
    configure_logging()
    api = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        summary="Moscow-first safe routing API for micromobility, robots, and sidewalk telemetry.",
        description=(
            "SafeRoute combines Photon search, Valhalla maneuvers, PostGIS/pgRouting safety scoring, "
            "and telemetry aggregation for a sidewalk digital twin."
        ),
        contact={"name": "SafeRoute Moscow"},
        license_info={"name": "Internal MVP"},
        openapi_tags=[
            {"name": "health", "description": "Dependency health, profile readiness, and runtime checks."},
            {"name": "observability", "description": "Prometheus-formatted runtime metrics for the local platform core."},
            {"name": "geocoding", "description": "Search and reverse geocoding through the SafeRoute gateway."},
            {"name": "routing", "description": "Real walk, bike, and car routes with Valhalla maneuvers and PostGIS safety enrichment."},
            {"name": "telemetry", "description": "Sidewalk telemetry ingestion and H3 aggregation for the digital sidewalk twin."},
            {"name": "compatibility", "description": "Temporary backwards-compatible aliases retained during contract migration."},
        ],
    )
    api.middleware("http")(request_logging_middleware)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    api.include_router(router)

    @api.get("/", include_in_schema=False)
    def read_index():
        if INDEX_FILE.exists():
            return FileResponse(INDEX_FILE)
        return JSONResponse({"status": "ok", "message": "SafeRoute API is running"})

    return api


app = create_app()
