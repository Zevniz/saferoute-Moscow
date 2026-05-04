from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.core.security import reset_rate_limit_state
from app.main import app
from app.schemas.routing import DependencyStatus, HealthResponse, Instruction, RouteFeature, ProfileReadiness, RouteProperties


def fake_route_feature(profile: str = "walk", mode: str = "safest") -> RouteFeature:
    instruction = Instruction(
        index=0,
        text="Идите прямо",
        distance_m=100,
        time_s=60,
        begin_shape_index=0,
        end_shape_index=1,
        type=1,
    )
    return RouteFeature(
        id=f"{profile}-safe",
        label="С более высокой оценкой",
        subtitle="Маршрут с учетом доступности",
        properties=RouteProperties(
            distance_m=1000,
            estimated_mins=12,
            safety_index=95,
            profile=profile,
            variant="safe",
            mode=mode,
            instructions=[instruction],
            bbox=[37.603, 55.7298, 37.6173, 55.7558],
            source="test",
        ),
        geometry={"type": "LineString", "coordinates": [[37.6173, 55.7558], [37.603, 55.7298]]},
    )


def test_openapi_exposes_expected_public_paths():
    paths = set(app.openapi()["paths"])

    assert "/api/search" in paths
    assert "/api/reverse" in paths
    assert "/api/route" in paths
    assert "/api/health" in paths
    assert "/api/metrics" in paths
    assert "/route" in paths
    assert "/api/telemetry/sidewalk-samples" in paths
    assert "/api/sidewalk-cells" in paths


def test_public_openapi_paths_do_not_require_authentication():
    spec = app.openapi()

    for path, method in [
        ("/api/search", "get"),
        ("/api/reverse", "get"),
        ("/api/route", "get"),
        ("/route", "get"),
        ("/api/health", "get"),
        ("/api/metrics", "get"),
        ("/api/telemetry/sidewalk-samples", "post"),
        ("/api/sidewalk-cells", "get"),
    ]:
        operation = spec["paths"][path][method]
        assert "security" not in operation


def test_route_rejects_invalid_coordinates_before_routing(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("build_route_set must not run for invalid coordinates")

    monkeypatch.setattr("app.api.routes.build_route_set", fail_if_called)
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=91&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=safest"
    )

    assert response.status_code == 422


def test_route_rejects_invalid_profile_before_routing(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("build_route_set must not run for invalid profile")

    monkeypatch.setattr("app.api.routes.build_route_set", fail_if_called)
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=scooter&mode=safest"
    )

    assert response.status_code == 422


def test_search_rejects_overlong_query_before_dependency_call(monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("search_places must not run for overlong queries")

    monkeypatch.setattr("app.api.routes.search_places", fail_if_called)
    client = TestClient(app)

    response = client.get(f"/api/search?q={'м' * 121}&limit=5")

    assert response.status_code == 422


def test_route_operational_observability_does_not_log_coordinates(monkeypatch):
    events = []
    counters = []
    observations = []

    def fake_build_route_set(profile, lat1, lon1, lat2, lon2, alternatives, *, mode):
        return [fake_route_feature(profile=profile, mode=mode)]

    monkeypatch.setattr("app.api.routes.build_route_set", fake_build_route_set)
    monkeypatch.setattr("app.api.routes.log_event", lambda event, **payload: events.append((event, payload)))
    monkeypatch.setattr("app.api.routes.inc", lambda name, labels=None, amount=1.0: counters.append((name, labels, amount)))
    monkeypatch.setattr("app.api.routes.observe", lambda name, value, labels=None: observations.append((name, value, labels)))
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=safest"
    )

    assert response.status_code == 200
    assert ("saferoute_route_requests_total", {"profile": "walk", "mode": "safest", "outcome": "ok"}, 1.0) in counters
    assert any(name == "saferoute_route_request_duration_ms" for name, _, _ in observations)
    route_event = next(payload for event, payload in events if event == "route_request")
    assert route_event["outcome"] == "ok"
    assert route_event["route_count"] == 1
    assert "lat1" not in route_event
    assert "lon1" not in route_event
    assert "origin" not in route_event
    assert "destination" not in route_event


def test_optional_metrics_api_key_is_disabled_by_default():
    client = TestClient(app)

    response = client.get("/api/metrics")

    assert response.status_code == 200


def test_optional_metrics_api_key_can_be_required(monkeypatch):
    class Settings:
        public_api_key_auth_enabled = True
        public_api_keys = ["secret-test-key"]
        require_api_key_for_metrics = True
        rate_limit_enabled = False

    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings())
    client = TestClient(app)

    rejected = client.get("/api/metrics")
    accepted = client.get("/api/metrics", headers={"x-saferoute-api-key": "secret-test-key"})

    assert rejected.status_code == 401
    assert accepted.status_code == 200


def test_saferoute_global_api_key_alias_protects_route(monkeypatch):
    class Settings:
        public_api_key_auth_enabled = False
        saferoute_require_api_key = True
        public_api_keys = ["secret-test-key"]
        rate_limit_enabled = False

    def fake_build_route_set(profile, lat1, lon1, lat2, lon2, alternatives, *, mode):
        return [fake_route_feature(profile=profile, mode=mode)]

    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings())
    monkeypatch.setattr("app.api.routes.build_route_set", fake_build_route_set)
    client = TestClient(app)
    url = "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=safest"

    missing = client.get(url)
    invalid = client.get(url, headers={"x-saferoute-api-key": "wrong"})
    accepted_header = client.get(url, headers={"x-saferoute-api-key": "secret-test-key"})
    accepted_bearer = client.get(url, headers={"Authorization": "Bearer secret-test-key"})

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert accepted_header.status_code == 200
    assert accepted_bearer.status_code == 200


def test_deep_health_can_be_protected_while_shallow_health_stays_public(monkeypatch):
    class Settings:
        public_api_key_auth_enabled = True
        saferoute_require_api_key = False
        public_api_keys = ["health-test-key"]
        require_api_key_for_deep_health = True
        rate_limit_enabled = False

    def fake_dependency_status(deep: bool = True) -> HealthResponse:
        return HealthResponse(
            status="ok",
            services={"postgres": DependencyStatus(status="ok")},
            profiles={"walk": ProfileReadiness(status="ok")} if deep else {},
        )

    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings())
    monkeypatch.setattr("app.api.routes.dependency_status", fake_dependency_status)
    client = TestClient(app)

    shallow = client.get("/api/health?deep=false")
    deep_missing_key = client.get("/api/health?deep=true")
    deep_valid_key = client.get("/api/health?deep=true", headers={"Authorization": "Bearer health-test-key"})

    assert shallow.status_code == 200
    assert deep_missing_key.status_code == 401
    assert deep_valid_key.status_code == 200


def test_global_api_key_requirement_keeps_shallow_health_public(monkeypatch):
    class Settings:
        public_api_key_auth_enabled = False
        saferoute_require_api_key = True
        public_api_keys = ["health-test-key"]
        require_api_key_for_deep_health = True
        rate_limit_enabled = False

    def fake_dependency_status(deep: bool = True) -> HealthResponse:
        return HealthResponse(
            status="ok",
            services={"postgres": DependencyStatus(status="ok")},
            profiles={"walk": ProfileReadiness(status="ok")} if deep else {},
        )

    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings())
    monkeypatch.setattr("app.api.routes.dependency_status", fake_dependency_status)
    client = TestClient(app)

    shallow = client.get("/api/health?deep=false")
    deep_missing_key = client.get("/api/health?deep=true")
    deep_valid_key = client.get("/api/health?deep=true", headers={"x-saferoute-api-key": "health-test-key"})

    assert shallow.status_code == 200
    assert deep_missing_key.status_code == 401
    assert deep_valid_key.status_code == 200


def test_optional_rate_limit_can_be_enabled(monkeypatch):
    class Settings:
        rate_limit_enabled = True
        rate_limit_window_seconds = 60
        rate_limit_metrics_per_window = 1
        rate_limit_route_per_window = 100
        rate_limit_geocode_per_window = 100
        rate_limit_telemetry_per_window = 100
        rate_limit_tiles_per_window = 100
        rate_limit_health_per_window = 100
        public_api_key_auth_enabled = False
        require_api_key_for_metrics = False

    reset_rate_limit_state()
    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings())
    client = TestClient(app)

    assert client.get("/api/metrics").status_code == 200
    assert client.get("/api/metrics").status_code == 429
    reset_rate_limit_state()


def test_optional_telemetry_body_size_limit(monkeypatch):
    class Settings:
        public_api_key_auth_enabled = False
        require_api_key_for_telemetry_write = False
        rate_limit_enabled = False
        telemetry_max_body_bytes = 10

    monkeypatch.setattr("app.core.security.get_settings", lambda: Settings())
    client = TestClient(app)

    response = client.post(
        "/api/telemetry/sidewalk-samples",
        json={
            "samples": [
                {
                    "device_id": "robot-1",
                    "captured_at": "2026-04-20T12:00:00Z",
                    "lat": 55.7558,
                    "lon": 37.6173,
                    "speed_mps": 1.1,
                    "source": "robot",
                }
            ]
        },
    )

    assert response.status_code == 413


def test_saferoute_security_env_aliases_enable_production_policy(monkeypatch):
    for name in [
        "ENVIRONMENT",
        "SAFEROUTE_ENV",
        "PUBLIC_API_KEY_AUTH_ENABLED",
        "SAFEROUTE_REQUIRE_API_KEY",
        "PUBLIC_API_KEYS",
        "SAFEROUTE_API_KEYS",
        "REQUIRE_API_KEY_FOR_METRICS",
        "REQUIRE_API_KEY_FOR_DEEP_HEALTH",
        "SAFEROUTE_PROTECT_DEEP_HEALTH",
        "REQUIRE_API_KEY_FOR_TILES",
        "REQUIRE_API_KEY_FOR_TELEMETRY_WRITE",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SAFEROUTE_ENV", "production")
    monkeypatch.setenv("SAFEROUTE_REQUIRE_API_KEY", "true")
    monkeypatch.setenv("SAFEROUTE_API_KEYS", "alpha,beta")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.public_api_key_auth_enabled is True
    assert settings.public_api_keys == ["alpha", "beta"]
    assert settings.require_api_key_for_metrics is True
    assert settings.require_api_key_for_deep_health is True
    assert settings.require_api_key_for_tiles is True
    assert settings.require_api_key_for_telemetry_write is True


def test_saferoute_rate_limit_alias_sets_bucket_defaults(monkeypatch):
    for name in [
        "SAFEROUTE_RATE_LIMIT_PER_MINUTE",
        "RATE_LIMIT_ROUTE_PER_WINDOW",
        "RATE_LIMIT_GEOCODE_PER_WINDOW",
        "RATE_LIMIT_TELEMETRY_PER_WINDOW",
        "RATE_LIMIT_TILES_PER_WINDOW",
        "RATE_LIMIT_METRICS_PER_WINDOW",
        "RATE_LIMIT_HEALTH_PER_WINDOW",
    ]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SAFEROUTE_RATE_LIMIT_PER_MINUTE", "7")
    monkeypatch.setenv("RATE_LIMIT_ROUTE_PER_WINDOW", "3")

    settings = Settings(_env_file=None)

    assert settings.rate_limit_route_per_window == 3
    assert settings.rate_limit_geocode_per_window == 7
    assert settings.rate_limit_telemetry_per_window == 7
    assert settings.rate_limit_tiles_per_window == 7
    assert settings.rate_limit_metrics_per_window == 7
    assert settings.rate_limit_health_per_window == 7


def test_root_returns_response():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code in {200, 404}


def test_metrics_endpoint_returns_prometheus_text():
    client = TestClient(app)

    response = client.get("/api/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    assert "saferoute_http_requests_total" in response.text


def test_request_id_header_is_propagated():
    client = TestClient(app)

    response = client.get("/api/metrics", headers={"x-request-id": "backend-readiness-test"})

    assert response.headers["x-request-id"] == "backend-readiness-test"


def test_coordinate_query_validation_rejects_invalid_latitude():
    client = TestClient(app)

    reverse_response = client.get("/api/reverse?lat=91&lon=37.6173")
    route_response = client.get("/api/route?lat1=55.7558&lon1=37.6173&lat2=-91&lon2=37.6030")

    assert reverse_response.status_code == 422
    assert route_response.status_code == 422


def test_route_rejects_unknown_mode_before_backend_work():
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=shortest"
    )

    assert response.status_code == 422


def test_route_rejects_unknown_profile_before_backend_work():
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=transit&mode=safest"
    )

    assert response.status_code == 422


def test_route_returns_404_when_no_real_candidates(monkeypatch):
    monkeypatch.setattr("app.api.routes.build_route_set", lambda *args, **kwargs: [])
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=safest"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Маршрут не найден для выбранного режима"


def test_route_maps_database_failure_to_503(monkeypatch):
    def fail_route_set(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    monkeypatch.setattr("app.api.routes.build_route_set", fail_route_set)
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=safest"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Не удалось обогатить маршруты данными безопасности"


def test_route_response_includes_requested_mode(monkeypatch):
    def fake_build_route_set(profile, lat1, lon1, lat2, lon2, alternatives, *, mode):
        instruction = Instruction(
            index=0,
            text="Идите прямо",
            distance_m=100,
            time_s=60,
            begin_shape_index=0,
            end_shape_index=1,
            type=1,
        )
        return [
            RouteFeature(
                id=f"{profile}-safe",
                label="С более высокой оценкой",
                subtitle="Маршрут с учетом доступности",
                properties=RouteProperties(
                    distance_m=1000,
                    estimated_mins=12,
                    safety_index=95,
                    profile=profile,
                    variant="safe",
                    mode=mode,
                    instructions=[instruction],
                    bbox=[37.603, 55.7298, 37.6173, 55.7558],
                    source="test",
                ),
                geometry={"type": "LineString", "coordinates": [[37.6173, 55.7558], [37.603, 55.7298]]},
            )
        ]

    monkeypatch.setattr("app.api.routes.build_route_set", fake_build_route_set)
    client = TestClient(app)

    response = client.get(
        "/api/route?lat1=55.7558&lon1=37.6173&lat2=55.7298&lon2=37.6030&profile=walk&mode=accessible"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["mode"] == "accessible"
    assert payload["routes"][0]["properties"]["mode"] == "accessible"


def test_openapi_route_mode_query_is_enum():
    spec = app.openapi()
    parameters = spec["paths"]["/api/route"]["get"]["parameters"]
    mode_parameter = next(parameter for parameter in parameters if parameter["name"] == "mode")
    schema = mode_parameter["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]

    assert set(schema["enum"]) == {"safest", "fastest", "balanced", "accessible"}


def test_route_properties_keep_safety_index_and_add_optional_score():
    schema = app.openapi()["components"]["schemas"]["RouteProperties"]

    assert "safety_index" in schema["required"]
    assert schema["properties"]["safety_index"]["type"] == "integer"
    assert "score" in schema["properties"]
    assert "score" not in schema["required"]


def test_route_response_mode_fields_are_documented_enums():
    schemas = app.openapi()["components"]["schemas"]
    route_properties_mode = schemas["RouteProperties"]["properties"]["mode"]
    route_meta_mode = schemas["RouteMeta"]["properties"]["mode"]
    score_mode = schemas["RouteScoreDetails"]["properties"]["mode"]

    assert set(route_properties_mode["enum"]) == {"safest", "fastest", "balanced", "accessible"}
    assert route_meta_mode["enum"] == route_properties_mode["enum"]
    assert score_mode["enum"] == route_properties_mode["enum"]


def test_search_rejects_queries_that_are_short_after_trimming():
    client = TestClient(app)

    response = client.get("/api/search?q=%20%20a%20&limit=5")

    assert response.status_code == 422
    assert response.json()["detail"] == "search query must contain at least 2 non-whitespace characters"


def test_tile_coordinates_are_bounded_before_database_query():
    client = TestClient(app)

    response = client.get("/tiles/1/2/0.pbf")

    assert response.status_code == 422
    assert response.json()["detail"] == "tile coordinates out of range for zoom"


def test_request_metrics_use_route_templates_for_dynamic_paths():
    client = TestClient(app)

    client.get("/tiles/1/2/0.pbf")
    response = client.get("/api/metrics")

    assert 'path="/tiles/{z}/{x}/{y}.pbf"' in response.text
