from app.core.config import get_settings
from app.services.scoring import RouteAttributeSummary, calculate_route_score
from app.services import weather


def test_weather_disabled_returns_no_factor(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SAFEROUTE_WEATHER_ENABLED", "false")

    assert weather.get_route_weather_risk({"type": "LineString", "coordinates": [[37.6, 55.7], [37.7, 55.8]]}) is None

    get_settings.cache_clear()


def test_weather_risk_uses_real_provider_payload_when_enabled(monkeypatch):
    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()
    monkeypatch.setenv("SAFEROUTE_WEATHER_ENABLED", "true")
    monkeypatch.setenv("SAFEROUTE_WEATHER_PROVIDER", "open_meteo")
    monkeypatch.setenv("SAFEROUTE_WEATHER_TIMEOUT_SECONDS", "2.5")

    def fake_request_json(method, url, *, params=None, json_body=None, timeout_seconds=None, connect_timeout_seconds=None):
        assert method == "GET"
        assert "latitude" in params
        assert "longitude" in params
        assert params["latitude"] == 55.75
        assert params["longitude"] == 37.65
        assert timeout_seconds == 2.5
        assert connect_timeout_seconds == 2.5
        return (
            {
                "current": {
                    "temperature_2m": -2.0,
                    "precipitation": 3.0,
                    "rain": 0.0,
                    "snowfall": 0.4,
                    "weather_code": 71,
                    "wind_gusts_10m": 42.0,
                    "visibility": 800.0,
                }
            },
            12.0,
        )

    monkeypatch.setattr(weather, "request_json", fake_request_json)

    result = weather.get_route_weather_risk({"type": "LineString", "coordinates": [[37.5, 55.6], [37.8, 55.9]]})

    assert result is not None
    assert result.risk > 0.5
    assert result.confidence == 1.0
    assert result.source["provider"] == "open_meteo"
    assert result.source["active"] is True
    assert result.source["sample_method"] == "route_bbox_centroid"

    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()


def test_weather_provider_alias_open_meteo_dash_is_supported(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SAFEROUTE_WEATHER_PROVIDER", "open-meteo")

    assert get_settings().weather_provider == "open_meteo"

    get_settings.cache_clear()


def test_weather_provider_success_with_benign_payload_returns_active_zero_risk(monkeypatch):
    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()
    monkeypatch.setenv("SAFEROUTE_WEATHER_ENABLED", "true")

    def benign_request_json(method, url, *, params=None, json_body=None, timeout_seconds=None, connect_timeout_seconds=None):
        return (
            {
                "current": {
                    "temperature_2m": 8.0,
                    "precipitation": 0.0,
                    "rain": 0.0,
                    "snowfall": 0.0,
                    "weather_code": 1,
                    "wind_gusts_10m": 12.0,
                    "visibility": 10000.0,
                }
            },
            6.0,
        )

    monkeypatch.setattr(weather, "request_json", benign_request_json)

    result = weather.get_route_weather_risk({"type": "LineString", "coordinates": [[37.6, 55.7], [37.7, 55.8]]})

    assert result is not None
    assert result.risk == 0.0
    assert result.source["active"] is True

    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()


def test_weather_provider_failure_degrades_without_reason(monkeypatch):
    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()
    monkeypatch.setenv("SAFEROUTE_WEATHER_ENABLED", "true")

    def failing_request_json(method, url, *, params=None, json_body=None, timeout_seconds=None, connect_timeout_seconds=None):
        raise RuntimeError("provider down")

    monkeypatch.setattr(weather, "request_json", failing_request_json)

    assert weather.get_route_weather_risk({"type": "LineString", "coordinates": [[37.6, 55.7], [37.7, 55.8]]}) is None

    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()


def test_weather_invalid_provider_payload_degrades_without_factor(monkeypatch):
    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()
    monkeypatch.setenv("SAFEROUTE_WEATHER_ENABLED", "true")

    def invalid_request_json(method, url, *, params=None, json_body=None, timeout_seconds=None, connect_timeout_seconds=None):
        return ({"current": {"weather_code": "unknown"}}, 7.0)

    monkeypatch.setattr(weather, "request_json", invalid_request_json)

    assert weather.get_route_weather_risk({"type": "LineString", "coordinates": [[37.6, 55.7], [37.7, 55.8]]}) is None

    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()


def test_weather_cache_reuses_provider_result_within_ttl(monkeypatch):
    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()
    monkeypatch.setenv("SAFEROUTE_WEATHER_ENABLED", "true")
    calls = 0

    def fake_request_json(method, url, *, params=None, json_body=None, timeout_seconds=None, connect_timeout_seconds=None):
        nonlocal calls
        calls += 1
        return (
            {
                "current": {
                    "temperature_2m": 3.0,
                    "precipitation": 0.3,
                    "rain": 0.3,
                    "snowfall": 0.0,
                    "weather_code": 61,
                    "wind_gusts_10m": 20.0,
                    "visibility": 5000.0,
                }
            },
            5.0,
        )

    monkeypatch.setattr(weather, "request_json", fake_request_json)
    geometry = {"type": "LineString", "coordinates": [[37.6, 55.7], [37.7, 55.8]]}

    first = weather.get_route_weather_risk(geometry)
    second = weather.get_route_weather_risk(geometry)

    assert first is not None
    assert second is first
    assert calls == 1

    get_settings.cache_clear()
    weather._WEATHER_CACHE.clear()


def test_weather_risk_formula_is_bounded():
    risk = weather.calculate_open_meteo_risk(
        {
            "temperature_2m": -15,
            "precipitation": 12,
            "rain": 3,
            "snowfall": 4,
            "weather_code": 99,
            "wind_gusts_10m": 80,
            "visibility": 100,
        }
    )

    assert risk == 1.0


def test_weather_scoring_is_proportional_to_risk_and_confidence():
    result = calculate_route_score(
        RouteAttributeSummary(avg_safety_weight=1.0, avg_weather_sensitive_risk=0.5, weather_confidence=0.5),
        "safest",
        "walk",
    )

    reason = next(item for item in result.reasons if item.code == "weather_sensitive_risk")
    assert reason.weight == 1.5
    assert result.factors["avg_weather_sensitive_risk"] == 0.5
    assert result.factors["weather_confidence"] == 0.5


def test_zero_weather_risk_has_source_factor_but_no_penalty_reason():
    result = calculate_route_score(
        RouteAttributeSummary(avg_safety_weight=1.0, avg_weather_sensitive_risk=0.0, weather_confidence=1.0),
        "safest",
        "walk",
    )

    assert result.factors["avg_weather_sensitive_risk"] == 0.0
    assert "weather_sensitive_risk" not in {reason.code for reason in result.reasons}
