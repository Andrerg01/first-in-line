"""Unit tests for MCP server Brave Search rate-limit helpers.

Covers:
- _parse_brave_ratelimit_reset  — header parsing, clamping, edge cases
- _search_brave                 — 429 retry logic, proactive sleep on
                                  per-second quota exhaustion, non-200
                                  error handling
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out optional third-party packages that are only installed inside the
# mcp-server Docker image so the module can be imported in the unit-test
# environment without those packages present.
# ---------------------------------------------------------------------------
if "duckduckgo_search" not in sys.modules:
    sys.modules["duckduckgo_search"] = MagicMock()

# ---------------------------------------------------------------------------
# Import the module under test (not the FastAPI app object)
# ---------------------------------------------------------------------------

import mcp_server.app.main as mcp_main


# ---------------------------------------------------------------------------
# _parse_brave_ratelimit_reset
# ---------------------------------------------------------------------------

class TestParseBraveRatelimitReset:
    """_parse_brave_ratelimit_reset parses the per-second reset value."""

    def test_typical_header_returns_first_value(self):
        assert mcp_main._parse_brave_ratelimit_reset("1, 1419704") == 1.0

    def test_single_value_header(self):
        assert mcp_main._parse_brave_ratelimit_reset("2") == 2.0

    def test_fractional_value(self):
        assert mcp_main._parse_brave_ratelimit_reset("0.5, 999") == 0.5

    def test_zero_clamps_to_minimum(self):
        # 0 would mean sleep(0) which is fine but we clamp to 0.1 for safety
        assert mcp_main._parse_brave_ratelimit_reset("0, 999") == pytest.approx(0.1)

    def test_large_value_clamps_to_cap(self):
        cap = mcp_main._BRAVE_SEARCH_RETRY_CAP
        assert mcp_main._parse_brave_ratelimit_reset("9999, 1") == pytest.approx(cap)

    def test_none_returns_default(self):
        assert mcp_main._parse_brave_ratelimit_reset(None) == 1.0

    def test_empty_string_returns_default(self):
        assert mcp_main._parse_brave_ratelimit_reset("") == 1.0

    def test_non_numeric_returns_default(self):
        assert mcp_main._parse_brave_ratelimit_reset("abc, 123") == 1.0

    def test_whitespace_around_value_is_handled(self):
        assert mcp_main._parse_brave_ratelimit_reset("  1  , 9999") == 1.0


# ---------------------------------------------------------------------------
# _search_brave — happy path
# ---------------------------------------------------------------------------

class TestSearchBraveHappyPath:
    """_search_brave returns ranked results on a successful 200 response."""

    def _make_200_response(self, results: list[dict], remaining: str = "1, 1000") -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Reset": "1, 9999",
        }
        resp.json.return_value = {"web": {"results": results}}
        return resp

    def test_returns_ranked_results(self):
        raw = [
            {"title": "A", "url": "https://example.com/a", "description": "Snippet A"},
            {"title": "B", "url": "https://example.com/b", "description": "Snippet B"},
        ]
        resp = self._make_200_response(raw)
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = resp
            results = mcp_main._search_brave("test query", max_results=10)

        assert len(results) == 2
        assert results[0].rank == 1
        assert results[0].url == "https://example.com/a"
        assert results[0].title == "A"
        assert results[1].rank == 2

    def test_count_capped_at_brave_max(self):
        """count param never exceeds _BRAVE_MAX_RESULTS."""
        resp = self._make_200_response([])
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls:
            get_mock = mock_client_cls.return_value.__enter__.return_value.get
            get_mock.return_value = resp
            mcp_main._search_brave("query", max_results=100)
            call_kwargs = get_mock.call_args
            assert call_kwargs[1]["params"]["count"] == mcp_main._BRAVE_MAX_RESULTS

    def test_missing_key_returns_empty(self):
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", ""):
            results = mcp_main._search_brave("test", max_results=5)
        assert results == []

    def test_proactive_sleep_when_per_second_remaining_is_zero(self):
        """Sleeps for the reset duration when per-second quota hits 0."""
        resp = self._make_200_response([], remaining="0, 1000")
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls, \
             patch("mcp_server.app.main.time.sleep") as mock_sleep:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = resp
            mcp_main._search_brave("test", max_results=5)
            mock_sleep.assert_called_once()
            wait = mock_sleep.call_args[0][0]
            assert 0.1 <= wait <= mcp_main._BRAVE_SEARCH_RETRY_CAP

    def test_no_sleep_when_per_second_remaining_is_nonzero(self):
        resp = self._make_200_response([], remaining="1, 1000")
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls, \
             patch("mcp_server.app.main.time.sleep") as mock_sleep:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = resp
            mcp_main._search_brave("test", max_results=5)
            mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# _search_brave — 429 retry logic
# ---------------------------------------------------------------------------

class TestSearchBrave429Retry:
    """_search_brave retries on HTTP 429 using X-RateLimit-Reset."""

    def _make_429_response(self, reset: str = "1, 9999") -> MagicMock:
        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {"X-RateLimit-Reset": reset}
        return resp

    def _make_200_response(self) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"X-RateLimit-Remaining": "1, 1000", "X-RateLimit-Reset": "1, 9999"}
        resp.json.return_value = {"web": {"results": [{"title": "T", "url": "https://x.com", "description": "d"}]}}
        return resp

    def test_retries_on_429_then_succeeds(self):
        """Returns results after a single 429 followed by a 200."""
        resp_429 = self._make_429_response()
        resp_200 = self._make_200_response()

        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls, \
             patch("mcp_server.app.main.time.sleep"):
            get_mock = mock_client_cls.return_value.__enter__.return_value.get
            get_mock.side_effect = [resp_429, resp_200]
            results = mcp_main._search_brave("query", max_results=5)

        assert len(results) == 1
        assert get_mock.call_count == 2

    def test_sleeps_for_reset_duration_on_429(self):
        """Sleeps for the per-second reset value before retrying."""
        resp_429 = self._make_429_response(reset="2, 9999")
        resp_200 = self._make_200_response()

        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls, \
             patch("mcp_server.app.main.time.sleep") as mock_sleep:
            get_mock = mock_client_cls.return_value.__enter__.return_value.get
            get_mock.side_effect = [resp_429, resp_200]
            mcp_main._search_brave("query", max_results=5)

        # sleep called with the reset value (2s) before the retry
        sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
        assert any(s == pytest.approx(2.0) for s in sleep_calls)

    def test_all_429s_returns_empty(self):
        """Returns [] after exhausting all retries with 429s."""
        resp_429 = self._make_429_response()

        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls, \
             patch("mcp_server.app.main.time.sleep"):
            get_mock = mock_client_cls.return_value.__enter__.return_value.get
            get_mock.return_value = resp_429
            results = mcp_main._search_brave("query", max_results=5)

        assert results == []
        assert get_mock.call_count == mcp_main._BRAVE_SEARCH_MAX_RETRIES


# ---------------------------------------------------------------------------
# _search_brave — non-429 error paths
# ---------------------------------------------------------------------------

class TestSearchBraveErrors:
    """_search_brave returns [] on non-429 HTTP errors and network errors."""

    def test_non_200_non_429_returns_empty(self):
        resp = MagicMock()
        resp.status_code = 403
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = resp
            results = mcp_main._search_brave("query", max_results=5)
        assert results == []

    def test_network_exception_returns_empty(self):
        import httpx
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = (
                httpx.ConnectError("connection refused")
            )
            results = mcp_main._search_brave("query", max_results=5)
        assert results == []

    def test_json_parse_error_returns_empty(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.headers = {"X-RateLimit-Remaining": "1, 1000", "X-RateLimit-Reset": "1, 9999"}
        resp.json.side_effect = ValueError("bad json")
        with patch.object(mcp_main, "_BRAVE_SEARCH_API_KEY", "test-key"), \
             patch("mcp_server.app.main.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.get.return_value = resp
            results = mcp_main._search_brave("query", max_results=5)
        assert results == []
