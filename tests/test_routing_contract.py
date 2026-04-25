from app.schemas.routing import Instruction, RouteFeature, RouteProperties
from app.services.routing import (
    assign_route_variants,
    build_route_feature,
    fetch_valhalla_routes,
    normalize_instruction,
    normalize_trip_route,
    route_cache_key,
    use_materialized_nodes,
)
from app.services.scoring import cost_expression, hard_avoid_filter_sql


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
