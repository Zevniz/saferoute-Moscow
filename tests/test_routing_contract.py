from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.schemas.routing import Instruction, RouteFeature, RouteProperties
from app.services.routing import (
    _ROUTE_CACHE,
    assign_route_variants,
    build_safe_route_query,
    build_route_set,
    build_route_feature,
    clear_route_metadata_caches,
    fetch_safe_geometry,
    fetch_valhalla_routes,
    normalize_instruction,
    normalize_trip_route,
    route_cache_key,
    safe_corridor_bounds,
    use_materialized_nodes,
)
from app.services.scoring import RouteScoreResult, RoutingMode, ScoreReason, cost_expression, hard_avoid_filter_sql


def route_data(name, minutes, safety, coordinates=None):
    return {
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates or [[37.1, 55.7], [37.2, 55.8]],
        },
        "distance_m": 1200,
        "estimated_mins": minutes,
        "safety_index": safety,
        "instructions": [
            Instruction(
                index=0,
                text=f"Манёвр {name}",
                distance_m=120,
                time_s=60,
                begin_shape_index=0,
                end_shape_index=1,
                type=1,
            )
        ],
        "source": name,
    }


def test_route_feature_preserves_real_instruction_contract():
    instruction = Instruction(
        index=0,
        text="Поверните направо",
        distance_m=42,
        time_s=30,
        begin_shape_index=0,
        end_shape_index=2,
        type=9,
    )
    feature = build_route_feature(
        "walk",
        "safe",
        {
            "geometry": {"type": "LineString", "coordinates": [[37.1, 55.7], [37.2, 55.8]]},
            "distance_m": 120,
            "estimated_mins": 2,
            "safety_index": 91,
            "instructions": [instruction],
            "source": "postgis+valhalla-trace",
        },
    )

    assert isinstance(feature, RouteFeature)
    assert isinstance(feature.properties, RouteProperties)
    assert feature.properties.variant == "safe"
    assert feature.properties.mode == "safest"
    assert feature.properties.navigable is True
    assert feature.properties.instructions[0].text == "Поверните направо"


def test_route_feature_records_requested_mode():
    feature = build_route_feature(
        "walk",
        "safe",
        route_data("accessible-safe", minutes=14, safety=96),
        mode="accessible",
    )

    assert feature.properties.mode == "accessible"


def test_route_feature_preserves_active_weather_score_metadata(monkeypatch):
    monkeypatch.setattr("app.services.routing.get_active_enrichment_public_metadata", lambda: {"active": False, "active_factors": []})
    data = route_data("weather-safe", minutes=14, safety=96)
    data["score"] = RouteScoreResult(
        mode=RoutingMode.SAFEST,
        total=93,
        safety_index=93,
        factors={"avg_weather_sensitive_risk": 0.5, "weather_confidence": 1.0},
        reasons=(
            ScoreReason(
                code="weather_sensitive_risk",
                impact="penalty",
                message="Real weather data indicates route-level weather risk.",
                value=0.5,
                weight=3.0,
            ),
        ),
        data_sources={"weather": {"active": True, "provider": "open_meteo", "risk": 0.5, "confidence": 1.0}},
    )

    feature = build_route_feature("walk", "safe", data)

    assert feature.properties.score is not None
    assert feature.properties.score.data_sources["weather"]["active"] is True
    assert feature.properties.score.data_sources["weather"]["provider"] == "open_meteo"
    assert feature.properties.score.factors["weather_confidence"] == 1.0


def test_route_feature_preserves_active_telemetry_score_metadata(monkeypatch):
    monkeypatch.setattr("app.services.routing.get_active_enrichment_public_metadata", lambda: {"active": False, "active_factors": []})
    data = route_data("telemetry-safe", minutes=14, safety=98)
    data["score"] = RouteScoreResult(
        mode=RoutingMode.SAFEST,
        total=100,
        safety_index=100,
        factors={"avg_telemetry_confidence": 0.9},
        reasons=(
            ScoreReason(
                code="telemetry_confidence",
                impact="positive",
                message="Sampled route edges have high telemetry confidence.",
                value=0.9,
                weight=3.0,
            ),
        ),
        data_sources={
            "telemetry": {
                "active": True,
                "source": "sidewalk_telemetry",
                "mapping_method": "route_h3_cells",
                "sample_count": 42,
                "cell_count": 3,
                "coverage_fraction": 0.6,
                "avg_confidence": 0.9,
            }
        },
    )

    feature = build_route_feature("walk", "safe", data)

    assert feature.properties.score is not None
    assert feature.properties.score.data_sources["telemetry"]["active"] is True
    assert feature.properties.score.data_sources["telemetry"]["source"] == "sidewalk_telemetry"
    assert feature.properties.score.factors["avg_telemetry_confidence"] == 0.9


def test_route_cache_key_separates_route_modes():
    safest = route_cache_key("walk", 55.7558, 37.6173, 55.7298, 37.603, 3, "safest")
    fastest = route_cache_key("walk", 55.7558, 37.6173, 55.7298, 37.603, 3, "fastest")

    assert safest != fastest


def test_valhalla_trip_without_maneuvers_is_not_navigable():
    trip = {
        "legs": [
            {
                "shape": "????",
                "summary": {"length": 1.0, "time": 60},
                "maneuvers": [],
            }
        ]
    }

    assert normalize_trip_route(trip, source="valhalla") is None


def test_valhalla_maneuver_without_instruction_text_is_dropped():
    assert normalize_instruction(0, {"length": 1.0, "time": 30}) is None

    trip = {
        "legs": [
            {
                "shape": "????",
                "summary": {"length": 1.0, "time": 60},
                "maneuvers": [
                    {"length": 0.5, "time": 20},
                    {"instruction": "Продолжайте движение", "length": 0.5, "time": 40},
                ],
            }
        ]
    }

    route = normalize_trip_route(trip, source="valhalla", profile="walk")

    assert route is not None
    assert [instruction.text for instruction in route["instructions"]] == ["Продолжайте движение"]


def test_route_variant_assignment_keeps_fastest_route_honest():
    safe_route = route_data("postgis-safe", minutes=8, safety=77, coordinates=[[37.1, 55.7], [37.11, 55.71]])
    candidates = [
        route_data("valhalla-safer", minutes=16, safety=81, coordinates=[[37.2, 55.8], [37.21, 55.81]]),
        route_data("valhalla-fast", minutes=15, safety=77, coordinates=[[37.3, 55.9], [37.31, 55.91]]),
    ]

    routes = assign_route_variants("car", safe_route=safe_route, candidates=candidates, alternatives=3)
    by_variant = {route.properties.variant: route for route in routes}

    assert by_variant["safe"].properties.safety_index == 81
    assert by_variant["fast"].properties.estimated_mins == 8
    assert by_variant["fast"].properties.estimated_mins == min(route.properties.estimated_mins for route in routes)
    assert len({str(route.geometry) for route in routes}) == len(routes)


def test_route_variant_assignment_omits_false_fast_when_safe_is_fastest():
    safe_route = route_data("postgis-safe", minutes=8, safety=90, coordinates=[[37.1, 55.7], [37.11, 55.71]])
    candidates = [
        route_data("valhalla-one", minutes=13, safety=80, coordinates=[[37.2, 55.8], [37.21, 55.81]]),
        route_data("valhalla-two", minutes=15, safety=78, coordinates=[[37.3, 55.9], [37.31, 55.91]]),
    ]

    routes = assign_route_variants("walk", safe_route=safe_route, candidates=candidates, alternatives=3)
    variants = [route.properties.variant for route in routes]

    assert variants == ["safe", "balanced"]


def test_route_set_keeps_valhalla_routes_when_safety_graph_is_down(monkeypatch):
    _ROUTE_CACHE.clear()
    candidates = [
        route_data("valhalla-one", minutes=9, safety=99, coordinates=[[37.1, 55.7], [37.11, 55.71]]),
        route_data("valhalla-two", minutes=12, safety=99, coordinates=[[37.2, 55.8], [37.21, 55.81]]),
    ]

    def fake_fetch_valhalla_routes(*args, **kwargs):
        return [dict(route) for route in candidates]

    def fail_score(*args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("database unavailable"))

    monkeypatch.setattr("app.services.routing.fetch_valhalla_routes", fake_fetch_valhalla_routes)
    monkeypatch.setattr("app.services.routing.score_route_geometry", fail_score)
    monkeypatch.setattr("app.services.routing.fetch_safe_geometry", lambda *args, **kwargs: None)

    routes = build_route_set("walk", 55.7001, 37.1001, 55.7101, 37.1101, 3, mode="safest")

    assert routes
    assert routes[0].label == "Маршрут Valhalla"
    assert "PostGIS-оценка безопасности" in routes[0].subtitle
    assert routes[0].properties.safety_index == 50
    assert routes[0].properties.score is None
    assert "unscored" in routes[0].properties.source
    assert routes[0].properties.navigable is True


def test_accessible_mode_balanced_pick_prioritizes_safety_then_distance():
    candidates = [
        route_data("shorter-less-safe", minutes=10, safety=70, coordinates=[[37.2, 55.8], [37.21, 55.81]]),
        route_data("longer-safer", minutes=15, safety=92, coordinates=[[37.3, 55.9], [37.31, 55.91]]),
    ]

    routes = assign_route_variants("walk", safe_route=None, candidates=candidates, alternatives=3, mode="accessible")
    by_variant = {route.properties.variant: route for route in routes}

    assert by_variant["safe"].properties.safety_index == 92
    assert by_variant["safe"].properties.mode == "accessible"


def test_mode_cost_expression_uses_real_graph_safety_factors():
    columns = {"length", "safety_weight", "highway", "width", "est_width", "maxspeed", "lanes"}

    sql = cost_expression("bike", "accessible", columns)

    assert "safety_weight" in sql
    assert "width" in sql
    assert "est_width" in sql
    assert "maxspeed" in sql
    assert "lanes" in sql
    assert "cycleway" in sql


def test_hard_avoid_filter_uses_forbidden_access_steps_and_highways():
    columns = {"access", "highway"}

    sql = hard_avoid_filter_sql("bike", "safest", columns)

    assert "access" in sql
    assert "steps" in sql
    assert "motorway" in sql
    assert "trunk" in sql


def test_valhalla_routes_logs_once(monkeypatch):
    calls = []

    def fake_fetch_dependency_json(*args, **kwargs):
        return (
            {
                "trip": {
                    "legs": [
                        {
                            "shape": "????",
                            "summary": {"length": 1.0, "time": 60},
                            "maneuvers": [{"instruction": "Идите прямо", "length": 1.0, "time": 60}],
                        }
                    ]
                }
            },
            12.3,
            "http://localhost:8002",
        )

    def fake_log_event(event, **payload):
        calls.append((event, payload))

    monkeypatch.setattr("app.services.routing.fetch_dependency_json", fake_fetch_dependency_json)
    monkeypatch.setattr("app.services.routing.log_event", fake_log_event)

    routes = fetch_valhalla_routes("walk", 55.75, 37.61, 55.73, 37.60, 3)

    assert len(routes) == 1
    assert [event for event, _ in calls].count("valhalla_routes") == 1


def test_materialized_node_detection_accepts_materialized_views(monkeypatch):
    clear_route_metadata_caches()
    statements = []

    class FakeResult:
        def scalar(self):
            return True

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, statement):
            statements.append(str(statement))
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr("app.services.routing.get_engine", lambda: FakeEngine())

    assert use_materialized_nodes() is True
    assert "pg_class" in statements[0]
    assert "relkind IN ('r', 'm', 'v')" in statements[0]


def test_safe_corridor_bounds_include_origin_and_destination():
    min_lon, min_lat, max_lon, max_lat = safe_corridor_bounds(55.7558, 37.6173, 55.7298, 37.603, 1500)

    assert min_lat <= 55.7558 <= max_lat
    assert min_lat <= 55.7298 <= max_lat
    assert min_lon <= 37.6173 <= max_lon
    assert min_lon <= 37.603 <= max_lon


def test_safe_route_query_omits_corridor_when_not_provided(monkeypatch):
    monkeypatch.setattr(
        "app.services.routing.get_network_columns",
        lambda: {"id", "u", "v", "length", "safety_weight", "highway", "source_x", "source_y", "target_x", "target_y"},
    )
    monkeypatch.setattr("app.services.routing.use_materialized_nodes", lambda: True)

    sql = build_safe_route_query("walk", "TRUE", mode="safest", algorithm="astar")

    assert "ST_MakeEnvelope" not in sql


def test_safe_route_query_adds_corridor_filter(monkeypatch):
    monkeypatch.setattr(
        "app.services.routing.get_network_columns",
        lambda: {"id", "u", "v", "length", "safety_weight", "highway", "source_x", "source_y", "target_x", "target_y"},
    )
    monkeypatch.setattr("app.services.routing.use_materialized_nodes", lambda: True)

    sql = build_safe_route_query(
        "walk",
        "TRUE",
        mode="safest",
        algorithm="astar",
        corridor_filter_sql="geometry && ST_MakeEnvelope(1, 2, 3, 4, 4326)",
    )

    assert "ST_MakeEnvelope(1, 2, 3, 4, 4326)" in sql
    assert "AND" in sql


def test_route_cache_key_changes_with_corridor_settings(monkeypatch):
    monkeypatch.setattr("app.services.routing.get_active_enrichment_version", lambda: "v1")
    first_settings = Settings().model_copy(update={"route_safe_corridor_min_meters": 1500})
    second_settings = Settings().model_copy(update={"route_safe_corridor_min_meters": 3000})

    monkeypatch.setattr("app.services.routing.get_settings", lambda: first_settings)
    first_key = route_cache_key("walk", 55.7558, 37.6173, 55.7298, 37.603, 3, "safest")

    monkeypatch.setattr("app.services.routing.get_settings", lambda: second_settings)
    second_key = route_cache_key("walk", 55.7558, 37.6173, 55.7298, 37.603, 3, "safest")

    assert first_key != second_key


def test_fetch_safe_geometry_falls_back_when_bounded_has_no_route(monkeypatch):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    calls = []

    def fake_fetch_scope(conn, profile, lat1, lon1, lat2, lon2, *, mode, scope, corridor_filter_sql):
        calls.append((scope, corridor_filter_sql))
        if scope == "bounded":
            return None, "no_route"
        return {"geometry": {"type": "LineString", "coordinates": [[37.6173, 55.7558], [37.603, 55.7298]]}, "distance_m": 3200}, None

    monkeypatch.setattr("app.services.routing.get_engine", lambda: FakeEngine())
    monkeypatch.setattr("app.services.routing.safe_corridor_filter_sql", lambda *args: "geometry && ST_MakeEnvelope(1, 2, 3, 4, 4326)")
    monkeypatch.setattr("app.services.routing._fetch_safe_geometry_scope", fake_fetch_scope)
    monkeypatch.setattr("app.services.routing.get_settings", lambda: Settings())

    result = fetch_safe_geometry("walk", 55.7558, 37.6173, 55.7298, 37.603, mode="safest")

    assert result is not None
    assert result["distance_m"] == 3200
    assert calls == [
        ("bounded", "geometry && ST_MakeEnvelope(1, 2, 3, 4, 4326)"),
        ("fallback", None),
    ]
