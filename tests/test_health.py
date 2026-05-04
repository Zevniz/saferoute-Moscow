from app.schemas.routing import DependencyStatus, ProfileReadiness
from app.services.health import build_runtime_readiness, redact_url_credentials


def test_redact_url_credentials_hides_database_password():
    redacted = redact_url_credentials("postgresql://saferoute:secret@db:5432/saferoute_db")

    assert redacted == "postgresql://saferoute:***@db:5432/saferoute_db"
    assert "secret" not in redacted


def test_redact_url_credentials_preserves_urls_without_passwords():
    url = "postgresql://artem@localhost:5433/artem"

    assert redact_url_credentials(url) == url


def test_runtime_readiness_marks_self_hosted_ready(monkeypatch):
    class Settings:
        environment = "production"
        allow_public_service_fallback = False

    monkeypatch.setattr("app.services.health.get_settings", lambda: Settings())

    runtime = build_runtime_readiness(
        "ok",
        {
            "postgres": DependencyStatus(status="ok"),
            "photon": DependencyStatus(status="ok"),
            "valhalla": DependencyStatus(status="ok"),
        },
        {"walk": ProfileReadiness(status="ok")},
    )

    assert runtime.readiness == "self_hosted_ready"
    assert runtime.production_like is True


def test_runtime_readiness_marks_public_fallback_as_dev_only(monkeypatch):
    class Settings:
        environment = "development"
        allow_public_service_fallback = True

    monkeypatch.setattr("app.services.health.get_settings", lambda: Settings())

    runtime = build_runtime_readiness(
        "degraded",
        {
            "postgres": DependencyStatus(status="ok"),
            "photon": DependencyStatus(status="fallback", detail="using https://photon.komoot.io"),
            "valhalla": DependencyStatus(status="ok"),
        },
        {},
    )

    assert runtime.readiness == "dev_fallback"
    assert runtime.production_like is False
    assert runtime.public_fallback_allowed is True
