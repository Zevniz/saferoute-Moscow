import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reject_invalid_route_graph_algorithm():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ROUTE_GRAPH_ALGORITHM="bellman-ford")


def test_settings_reject_invalid_pool_size():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, DB_POOL_SIZE=0)


def test_settings_reject_invalid_telemetry_default_resolution():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, TELEMETRY_DEFAULT_H3_RESOLUTION=13)


def test_settings_accept_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

    settings = Settings(_env_file=None)

    assert settings.cors_allowed_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_settings_accept_json_cors_origins(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", '["http://localhost:5173","http://127.0.0.1:5173"]')

    settings = Settings(_env_file=None)

    assert settings.cors_allowed_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
