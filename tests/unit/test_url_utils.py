"""Unit tests for worker URL canonicalization utilities."""
import pytest

from worker.app.url_utils import canonicalize_url, is_valid_http_url


class TestCanonicalizeUrl:
    """Tests for canonicalize_url()."""

    def test_lowercases_scheme_and_host(self):
        assert canonicalize_url("HTTPS://Example.COM/path") == "https://example.com/path"

    def test_strips_trailing_slash_from_path(self):
        assert canonicalize_url("https://example.com/path/") == "https://example.com/path"

    def test_preserves_root_slash(self):
        result = canonicalize_url("https://example.com/")
        assert result == "https://example.com/"

    def test_removes_utm_params(self):
        url = "https://example.com/page?utm_source=twitter&utm_campaign=launch&q=test"
        result = canonicalize_url(url)
        assert "utm_source" not in result
        assert "utm_campaign" not in result
        assert "q=test" in result

    def test_removes_fbclid(self):
        url = "https://example.com/?fbclid=ABC123&id=1"
        result = canonicalize_url(url)
        assert "fbclid" not in result
        assert "id=1" in result

    def test_removes_fragment(self):
        url = "https://example.com/page#section"
        result = canonicalize_url(url)
        assert "#" not in result

    def test_sorts_query_params(self):
        url1 = canonicalize_url("https://example.com/?z=last&a=first")
        url2 = canonicalize_url("https://example.com/?a=first&z=last")
        assert url1 == url2

    def test_strips_default_http_port(self):
        assert canonicalize_url("http://example.com:80/") == "http://example.com/"

    def test_strips_default_https_port(self):
        assert canonicalize_url("https://example.com:443/page") == "https://example.com/page"

    def test_keeps_non_default_port(self):
        result = canonicalize_url("https://example.com:8443/page")
        assert ":8443" in result

    def test_returns_original_on_parse_failure(self):
        bad = "not_a_valid_url"
        # Should not raise; returns something reasonable
        result = canonicalize_url(bad)
        assert isinstance(result, str)


class TestIsValidHttpUrl:
    """Tests for is_valid_http_url()."""

    def test_valid_https(self):
        assert is_valid_http_url("https://example.com/path") is True

    def test_valid_http(self):
        assert is_valid_http_url("http://example.com") is True

    def test_rejects_ftp(self):
        assert is_valid_http_url("ftp://example.com") is False

    def test_rejects_no_scheme(self):
        assert is_valid_http_url("example.com/path") is False

    def test_rejects_empty(self):
        assert is_valid_http_url("") is False
