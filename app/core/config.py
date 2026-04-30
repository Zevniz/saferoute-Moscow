"""Application settings for SafeRoute.

The production default is a self-hosted runtime. Public Photon/Valhalla
endpoints are available only when explicitly enabled for local development.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, List

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, DotEnvSettingsSource, EnvSettingsSource, PydanticBaseSettingsSource, SettingsConfigDict


class CorsOriginsEnvSettingsSource(EnvSettingsSource):
    """Let the CORS validator parse JSON or comma-separated env values."""

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        if field_name in {"cors_allowed_origins", "public_api_keys"}:
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class CorsOriginsDotEnvSettingsSource(DotEnvSettingsSource):
    """Let the CORS validator parse JSON or comma-separated `.env` values."""

    def prepare_field_value(self, field_name: str, field: FieldInfo, value: Any, value_is_complex: bool) -> Any:
        if field_name in {"cors_allowed_origins", "public_api_keys"}:
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
    environment: str = Field(default="development", validation_alias=AliasChoices("SAFEROUTE_ENV", "ENVIRONMENT"))

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
    route_safe_corridor_enabled: bool = Field(default=True, validation_alias="ROUTE_SAFE_CORRIDOR_ENABLED")
    route_safe_corridor_min_meters: int = Field(default=1500, ge=0, validation_alias="ROUTE_SAFE_CORRIDOR_MIN_METERS")
    route_safe_corridor_direct_distance_ratio: float = Field(
        default=0.6,
        ge=0,
        validation_alias="ROUTE_SAFE_CORRIDOR_DIRECT_DISTANCE_RATIO",
    )
    route_safe_corridor_max_meters: int = Field(default=8000, ge=0, validation_alias="ROUTE_SAFE_CORRIDOR_MAX_METERS")
    route_safe_corridor_fallback_enabled: bool = Field(default=True, validation_alias="ROUTE_SAFE_CORRIDOR_FALLBACK_ENABLED")
    health_route_readiness: bool = Field(default=True, validation_alias="HEALTH_ROUTE_READINESS")

    weather_enabled: bool = Field(default=False, validation_alias="SAFEROUTE_WEATHER_ENABLED")
    weather_provider: str = Field(default="open_meteo", validation_alias="SAFEROUTE_WEATHER_PROVIDER")
    weather_cache_ttl_seconds: int = Field(default=900, ge=60, validation_alias="SAFEROUTE_WEATHER_CACHE_TTL_SECONDS")
    weather_timeout_seconds: float = Field(default=3.0, gt=0, validation_alias="SAFEROUTE_WEATHER_TIMEOUT_SECONDS")
    weather_api_key: str = Field(default="", validation_alias="SAFEROUTE_WEATHER_API_KEY")
    weather_url: str = Field(default="https://api.open-meteo.com/v1/forecast", validation_alias="SAFEROUTE_WEATHER_URL")

    telemetry_default_h3_resolution: int = Field(default=9, ge=7, le=12, validation_alias="TELEMETRY_DEFAULT_H3_RESOLUTION")
    telemetry_max_batch_size: int = Field(default=500, ge=1, validation_alias="TELEMETRY_MAX_BATCH_SIZE")
    telemetry_max_body_bytes: int = Field(
        default=262_144,
        ge=1024,
        validation_alias=AliasChoices("SAFEROUTE_MAX_TELEMETRY_PAYLOAD_BYTES", "TELEMETRY_MAX_BODY_BYTES"),
    )
    sidewalk_cells_limit: int = Field(default=5000, ge=1, validation_alias="SIDEWALK_CELLS_LIMIT")

    public_api_key_auth_enabled: bool = Field(default=False, validation_alias="PUBLIC_API_KEY_AUTH_ENABLED")
    saferoute_require_api_key: bool = Field(default=False, validation_alias="SAFEROUTE_REQUIRE_API_KEY")
    public_api_keys: List[str] = Field(default_factory=list, validation_alias=AliasChoices("SAFEROUTE_API_KEYS", "PUBLIC_API_KEYS"))
    require_api_key_for_metrics: bool = Field(default=False, validation_alias="REQUIRE_API_KEY_FOR_METRICS")
    require_api_key_for_deep_health: bool = Field(
        default=False,
        validation_alias=AliasChoices("SAFEROUTE_PROTECT_DEEP_HEALTH", "REQUIRE_API_KEY_FOR_DEEP_HEALTH"),
    )
    require_api_key_for_tiles: bool = Field(default=False, validation_alias="REQUIRE_API_KEY_FOR_TILES")
    require_api_key_for_telemetry_write: bool = Field(default=False, validation_alias="REQUIRE_API_KEY_FOR_TELEMETRY_WRITE")
    rate_limit_enabled: bool = Field(default=False, validation_alias=AliasChoices("SAFEROUTE_RATE_LIMIT_ENABLED", "RATE_LIMIT_ENABLED"))
    saferoute_rate_limit_per_minute: int | None = Field(default=None, ge=1, validation_alias="SAFEROUTE_RATE_LIMIT_PER_MINUTE")
    rate_limit_window_seconds: int = Field(default=60, ge=1, validation_alias="RATE_LIMIT_WINDOW_SECONDS")
    rate_limit_route_per_window: int = Field(default=60, ge=1, validation_alias="RATE_LIMIT_ROUTE_PER_WINDOW")
    rate_limit_geocode_per_window: int = Field(default=120, ge=1, validation_alias="RATE_LIMIT_GEOCODE_PER_WINDOW")
    rate_limit_telemetry_per_window: int = Field(default=60, ge=1, validation_alias="RATE_LIMIT_TELEMETRY_PER_WINDOW")
    rate_limit_tiles_per_window: int = Field(default=600, ge=1, validation_alias="RATE_LIMIT_TILES_PER_WINDOW")
    rate_limit_metrics_per_window: int = Field(default=60, ge=1, validation_alias="RATE_LIMIT_METRICS_PER_WINDOW")
    rate_limit_health_per_window: int = Field(default=120, ge=1, validation_alias="RATE_LIMIT_HEALTH_PER_WINDOW")

    @model_validator(mode="after")
    def apply_saferoute_public_launch_aliases(self) -> "Settings":
        """Apply coarse SAFEROUTE_* knobs without removing canonical env names."""

        if self.saferoute_require_api_key:
            self.public_api_key_auth_enabled = True
            self.require_api_key_for_metrics = True
            self.require_api_key_for_deep_health = True
            self.require_api_key_for_tiles = True
            self.require_api_key_for_telemetry_write = True

        if self.saferoute_rate_limit_per_minute is not None:
            generic_limit = self.saferoute_rate_limit_per_minute
            specific_envs = {
                "rate_limit_route_per_window": "RATE_LIMIT_ROUTE_PER_WINDOW",
                "rate_limit_geocode_per_window": "RATE_LIMIT_GEOCODE_PER_WINDOW",
                "rate_limit_telemetry_per_window": "RATE_LIMIT_TELEMETRY_PER_WINDOW",
                "rate_limit_tiles_per_window": "RATE_LIMIT_TILES_PER_WINDOW",
                "rate_limit_metrics_per_window": "RATE_LIMIT_METRICS_PER_WINDOW",
                "rate_limit_health_per_window": "RATE_LIMIT_HEALTH_PER_WINDOW",
            }
            for field_name, env_name in specific_envs.items():
                if env_name not in os.environ:
                    setattr(self, field_name, generic_limit)
        return self

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

    @field_validator("public_api_keys", mode="before")
    @classmethod
    def split_api_keys(cls, value: object) -> object:
        """Allow JSON-array and comma-separated API keys in env files."""

        if value is None or value == "":
            return []
        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return []
            if raw_value.startswith("["):
                try:
                    parsed = json.loads(raw_value)
                except json.JSONDecodeError as exc:
                    raise ValueError("SAFEROUTE_API_KEYS/PUBLIC_API_KEYS must be a JSON array or comma-separated list") from exc
                if not isinstance(parsed, list):
                    raise ValueError("SAFEROUTE_API_KEYS/PUBLIC_API_KEYS JSON value must be an array")
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [item.strip() for item in raw_value.split(",") if item.strip()]
        return value

    @field_validator("weather_provider")
    @classmethod
    def normalize_weather_provider(cls, value: str) -> str:
        """Normalize provider env aliases while rejecting unsupported values."""

        normalized = value.strip().lower().replace("-", "_")
        if normalized != "open_meteo":
            raise ValueError("SAFEROUTE_WEATHER_PROVIDER must be 'open_meteo'")
        return normalized

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
