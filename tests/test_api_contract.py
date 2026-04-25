from fastapi.testclient import TestClient

from app.main import app
from app.schemas.routing import Instruction, RouteFeature, RouteProperties


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
                label="Наиболее безопасный",
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
