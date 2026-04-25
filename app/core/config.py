"""Application settings for SafeRoute.

The production default is a self-hosted runtime. Public Photon/Valhalla
endpoints are available only when explicitly enabled for local development.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, List

from pydantic import Field, field_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


class CorsOriginsEnvSettingsSource(EnvSettingsSource):
    """Let the CORS validator parse JSON or comma-separated env values."""

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        if field_name == "cors_allowed_origins":
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CorsOriginsDotEnvSettingsSource(DotEnvSettingsSource):
    """Let the CORS validator parse JSON or comma-separated `.env` values."""

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        if field_name == "cors_allowed_origins":
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    """Environment-driven runtime configuration."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize only CORS origin env parsing while preserving defaults."""

        return (
            init_settings,
            CorsOriginsEnvSettingsSource(settings_cls),
            CorsOriginsDotEnvSettingsSource(settings_cls),
            file_secret_settings,
        )

    app_name: str = "SafeRoute Moscow"
    app_version: str = "2.1.0"
    environment: str = Field(default="development", validation_alias="ENVIRONMENT")

    database_url: str = Field(default="postgresql://artem@localhost:5433/artem", validation_alias="DATABASE_URL")
    db_pool_size: int = Field(default=5, gt=0, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, ge=0, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=10, gt=0, validation_alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, ge=0, validation_alias="DB_POOL_RECYCLE")

    photon_url: str = Field(default="http://localhost:2322", validation_alias="PHOTON_URL")
    valhalla_url: str = Field(default="http://localhost:8002", validation_alias="VALHALLA_URL")
    public_photon_url: str = Field(default="https://photon.komoot.io", validation_alias="PUBLIC_PHOTON_URL")
    public_valhalla_url: str = Field(default="https://valhalla1.openstreetmap.de", validation_alias="PUBLIC_VALHALLA_URL")
    allow_public_service_fallback: bool = Field(default=False, validation_alias="ALLOW_PUBLIC_SERVICE_FALLBACK")
    http_user_agent: str = Field(default="SafeRoute/2.1 production-mvp", validation_alias="HTTP_USER_AGENT")
    http_timeout_seconds: float = Field(default=20.0, gt=0, validation_alias="HTTP_TIMEOUT_SECONDS")
    http_connect_timeout_seconds: float = Field(default=10.0, gt=0, validation_alias="HTTP_CONNECT_TIMEOUT_SECONDS")
    http_retry_attempts: int = Field(default=2, ge=1, validation_alias="HTTP_RETRY_ATTEMPTS")
    http_retry_backoff_seconds: float = Field(default=0.25, ge=0, validation_alias="HTTP_RETRY_BACKOFF_SECONDS")

    cors_allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        validation_alias="CORS_ALLOWED_ORIGINS",
    )

    moscow_min_lat: float = Field(default=55.45, validation_alias="MOSCOW_MIN_LAT")
    moscow_max_lat: float = Field(default=56.02, validation_alias="MOSCOW_MAX_LAT")
    moscow_min_lon: float = Field(default=37.10, validation_alias="MOSCOW_MIN_LON")
    moscow_max_lon: float = Field(default=38.05, validation_alias="MOSCOW_MAX_LON")

    route_cache_ttl_seconds: int = Field(default=120, ge=0, validation_alias="ROUTE_CACHE_TTL_SECONDS")
    route_cache_max_entries: int = Field(default=256, ge=1, validation_alias="ROUTE_CACHE_MAX_ENTRIES")
    route_bucket_precision: int = Field(default=4, ge=0, le=8, validation_alias="ROUTE_BUCKET_PRECISION")
    route_data_version: str = Field(default="moscow-network-v1", validation_alias="ROUTE_DATA_VERSION")
    route_graph_algorithm: str = Field(default="astar", validation_alias="ROUTE_GRAPH_ALGORITHM")
    health_route_readiness: bool = Field(default=True, validation_alias="HEALTH_ROUTE_READINESS")

    telemetry_default_h3_resolution: int = Field(default=9, ge=7, le=12, validation_alias="TELEMETRY_DEFAULT_H3_RESOLUTION")
    telemetry_max_batch_size: int = Field(default=500, ge=1, validation_alias="TELEMETRY_MAX_BATCH_SIZE")
    sidewalk_cells_limit: int = Field(default=5000, ge=1, validation_alias="SIDEWALK_CELLS_LIMIT")

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        """Allow JSON-array and comma-separated origins in `.env` files."""

        if isinstance(value, str):
            raw_value = value.strip()
            if raw_value.startswith("["):
                try:
                    parsed = json.loads(raw_value)
                except json.JSONDecodeError as exc:
                    raise ValueError("CORS_ALLOWED_ORIGINS must be a JSON array or comma-separated list") from exc
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ALLOWED_ORIGINS JSON value must be an array")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        return value

    @field_validator("route_graph_algorithm")
    @classmethod
    def validate_route_graph_algorithm(cls, value: str) -> str:
        """Reject mistyped graph algorithms instead of silently changing behavior."""

        normalized = value.lower()
        if normalized not in {"astar", "dijkstra"}:
            raise ValueError("ROUTE_GRAPH_ALGORITHM must be 'astar' or 'dijkstra'")
        return normalized


@lru_cache
def get_settings() -> Settings:
    """Return cached settings for the process."""

    return Settings()
