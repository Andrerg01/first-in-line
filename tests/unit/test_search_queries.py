"""Unit tests for worker search query templates."""
from worker.app.search_queries import QUERY_SET_VERSION, get_queries


def test_get_queries_returns_list_of_strings():
    queries = get_queries()
    assert isinstance(queries, list)
    assert len(queries) > 0
    for q in queries:
        assert isinstance(q, str)
        assert len(q) > 0


def test_default_location_is_greenville_sc():
    queries = get_queries()
    for q in queries:
        assert "Greenville" in q and "SC" in q, f"Expected Greenville SC in {q!r}"


def test_custom_location_is_substituted():
    queries = get_queries(location="Charleston SC")
    for q in queries:
        assert "Charleston SC" in q
        assert "Greenville SC" not in q


def test_query_set_version_is_string():
    assert isinstance(QUERY_SET_VERSION, str)
    assert len(QUERY_SET_VERSION) > 0


def test_queries_cover_key_categories():
    queries = get_queries()
    combined = " ".join(queries).lower()
    assert "restaurant" in combined
    assert "grand opening" in combined
