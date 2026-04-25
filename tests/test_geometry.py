from app.services.geometry import geometry_bounds, orient_geometry, sampling_line_geometry
from app.services.routing import calculate_safety_index


def test_geometry_bounds_supports_linestring_and_multilinestring():
    line = {"type": "LineString", "coordinates": [[37.1, 55.7], [37.3, 55.9]]}
    multi = {"type": "MultiLineString", "coordinates": [[[37.1, 55.7]], [[37.4, 55.8], [37.2, 55.6]]]}

    assert geometry_bounds(line) == [37.1, 55.7, 37.3, 55.9]
    assert geometry_bounds(multi) == [37.1, 55.6, 37.4, 55.8]


def test_sampling_line_geometry_flattens_multiline():
    multi = {"type": "MultiLineString", "coordinates": [[[1, 2], [3, 4]], [[5, 6]]]}

    assert sampling_line_geometry(multi) == {"type": "LineString", "coordinates": [[1, 2], [3, 4], [5, 6]]}


def test_orient_geometry_reverses_when_destination_is_first():
    geometry = {"type": "LineString", "coordinates": [[10, 10], [9, 9], [8, 8]]}

    oriented = orient_geometry(geometry, lat1=8, lon1=8, lat2=10, lon2=10)

    assert oriented["coordinates"][0] == [8, 8]
    assert oriented["coordinates"][-1] == [10, 10]


def test_safety_index_clamps_weight_range():
    assert calculate_safety_index(1.0) == 100
    assert calculate_safety_index(5.0) == 0
    assert calculate_safety_index(9.0) == 0
    assert calculate_safety_index(None) == 100

