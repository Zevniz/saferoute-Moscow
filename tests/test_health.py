from app.services.health import redact_url_credentials


def test_redact_url_credentials_hides_database_password():
    redacted = redact_url_credentials("postgresql://saferoute:secret@db:5432/saferoute_db")

    assert redacted == "postgresql://saferoute:***@db:5432/saferoute_db"
    assert "secret" not in redacted


def test_redact_url_credentials_preserves_urls_without_passwords():
    url = "postgresql://artem@localhost:5433/artem"

    assert redact_url_credentials(url) == url

