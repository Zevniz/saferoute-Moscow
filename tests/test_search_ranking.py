from app.services.search import local_landmark_matches, merge_ranked_results
from app.schemas.routing import SearchResult


def test_kremlin_landmark_is_ranked_as_canonical_moscow_poi():
    matches = local_landmark_matches("Кремль", 5)

    assert matches[0].id == "landmark:moscow-kremlin"
    assert matches[0].label == "Московский Кремль, Москва"
    assert matches[0].kind == "landmark"


def test_ranked_result_merge_keeps_order_and_deduplicates():
    primary = [
        SearchResult(id="a", label="A", lat=55.7, lon=37.6),
        SearchResult(id="b", label="B", lat=55.7, lon=37.6),
    ]
    secondary = [
        SearchResult(id="a", label="A duplicate", lat=55.7, lon=37.6),
        SearchResult(id="c", label="C", lat=55.7, lon=37.6),
    ]

    merged = merge_ranked_results(primary, secondary, 3)

    assert [item.id for item in merged] == ["a", "b", "c"]
