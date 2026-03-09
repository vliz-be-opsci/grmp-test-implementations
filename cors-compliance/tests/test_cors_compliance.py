#!/usr/bin/env python3
"""
Unit tests for cors_compliance.py

Run with (from cors-compliance/ root):
    pip install pytest requests junitparser
    pytest tests/test_cors_compliance.py -v
"""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from cors_compliance import (
    _parse_list_env,
    _parse_origins,
    _follow_to_final,
    parse_config,
    run_allow_origin_test,
    run_allow_methods_test,
    run_allow_headers_test,
    run_expose_headers_test,
    run_https_redirect_test,
    run_tests_for_url,
    skipped_test,
    create_junit_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_response(status_code=200, headers=None, url="https://example.com"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.url = url
    return resp


def make_redirect_response(status_code, location, url="http://example.com"):
    return make_response(status_code=status_code, headers={"Location": location}, url=url)


def _config(**overrides):
    base = {
        "timeout": 10,
        "probe_origin": "https://vliz.be",
        "origins": ["*"],
        "allow_methods": ["GET", "HEAD", "OPTIONS"],
        "allow_headers": ["Accept"],
        "expose_headers": ["Content-Type", "Link"],
        "https_redirect": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _parse_list_env
# ---------------------------------------------------------------------------

class TestParseListEnv:
    def test_returns_default_when_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_FOO", raising=False)
        assert _parse_list_env("TEST_FOO", ["a"]) == ["a"]

    def test_parses_list_literal(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "['x', 'y']")
        assert _parse_list_env("TEST_FOO", []) == ["x", "y"]

    def test_wraps_bare_string_in_list(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "'single'")
        assert _parse_list_env("TEST_FOO", []) == ["single"]

    def test_invalid_value_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "not valid{{")
        assert _parse_list_env("TEST_FOO", ["default"]) == ["default"]

    def test_filters_empty_strings(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "['a', '', 'b']")
        assert _parse_list_env("TEST_FOO", []) == ["a", "b"]

    def test_non_list_type_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "42")
        assert _parse_list_env("TEST_FOO", ["default"]) == ["default"]


# ---------------------------------------------------------------------------
# _parse_origins
# ---------------------------------------------------------------------------

class TestParseOrigins:
    def test_wildcard_is_valid(self):
        origins, error = _parse_origins(["*"])
        assert origins == ["*"]
        assert error is None

    def test_specific_origins_are_valid(self):
        origins, error = _parse_origins(["https://vliz.be", "https://github.com"])
        assert error is None
        assert "https://vliz.be" in origins

    def test_mixed_wildcard_and_specific_is_invalid(self):
        origins, error = _parse_origins(["*", "https://vliz.be"])
        assert origins is None
        assert error is not None

    def test_empty_list_returns_none_for_lenient_mode(self):
        origins, error = _parse_origins([])
        assert origins is None
        assert error is None

    def test_none_input_returns_none_for_lenient_mode(self):
        origins, error = _parse_origins(None)
        assert origins is None
        assert error is None


# ---------------------------------------------------------------------------
# parse_config
# ---------------------------------------------------------------------------

class TestParseConfig:
    ENV_KEYS = [
        "TEST_URLS", "TEST_ACCESS-CONTROL-ALLOW-ORIGIN",
        "TEST_ACCESS-CONTROL-ALLOW-METHODS", "TEST_ACCESS-CONTROL-ALLOW-HEADERS",
        "TEST_ACCESS-CONTROL-EXPOSE-HEADERS", "TEST_HTTPS-REDIRECT",
        "TEST_PROBE-ORIGIN", "TEST_TIMEOUT", "SPECIAL_SOURCE_FILE",
    ]

    def _clean(self, monkeypatch):
        for k in self.ENV_KEYS:
            monkeypatch.delenv(k, raising=False)

    def test_defaults(self, monkeypatch):
        self._clean(monkeypatch)
        config = parse_config()
        assert config["urls"] == []
        assert config["origins"] is None  # lenient mode by default
        assert config["allow_methods"] == ["GET", "HEAD", "OPTIONS"]
        assert config["allow_headers"] == ["Accept"]
        assert config["expose_headers"] == ["Content-Type", "Link"]
        assert config["https_redirect"] is False
        assert config["probe_origin"] == "https://vliz.be"
        assert config["timeout"] == 30
        assert config["provenance"] == "unknown"

    def test_custom_urls(self, monkeypatch):
        monkeypatch.setenv("TEST_URLS", "['https://example.com']")
        assert parse_config()["urls"] == ["https://example.com"]

    def test_custom_origins(self, monkeypatch):
        monkeypatch.setenv("TEST_ACCESS-CONTROL-ALLOW-ORIGIN", "['https://vliz.be']")
        assert parse_config()["origins"] == ["https://vliz.be"]

    def test_mixed_origins_falls_back_to_lenient(self, monkeypatch):
        monkeypatch.setenv("TEST_ACCESS-CONTROL-ALLOW-ORIGIN", "['*', 'https://vliz.be']")
        assert parse_config()["origins"] is None

    def test_https_redirect_true(self, monkeypatch):
        monkeypatch.setenv("TEST_HTTPS-REDIRECT", "true")
        assert parse_config()["https_redirect"] is True

    def test_https_redirect_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("TEST_HTTPS-REDIRECT", "True")
        assert parse_config()["https_redirect"] is True

    def test_custom_probe_origin(self, monkeypatch):
        monkeypatch.setenv("TEST_PROBE-ORIGIN", "https://custom.org")
        assert parse_config()["probe_origin"] == "https://custom.org"

    def test_invalid_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "not-a-number")
        assert parse_config()["timeout"] == 30

    def test_zero_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "0")
        assert parse_config()["timeout"] == 30

    def test_negative_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "-5")
        assert parse_config()["timeout"] == 30

    def test_provenance_from_env(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "my-config.yaml")
        assert parse_config()["provenance"] == "my-config.yaml"


# ---------------------------------------------------------------------------
# _follow_to_final
# ---------------------------------------------------------------------------

class TestFollowToFinal:
    def test_no_redirect_returns_response(self):
        resp = make_response(200)
        with patch("cors_compliance.requests.request", return_value=resp):
            final, chain, err = _follow_to_final("GET", "https://example.com", {}, 10)
        assert err is None
        assert chain == []
        assert final.status_code == 200

    def test_follows_single_redirect(self):
        redirect = make_redirect_response(301, "https://example.com/new", "http://example.com")
        final = make_response(200, url="https://example.com/new")
        responses = iter([redirect, final])
        with patch("cors_compliance.requests.request", side_effect=lambda *a, **kw: next(responses)):
            result, chain, err = _follow_to_final("GET", "http://example.com", {}, 10)
        assert err is None
        assert len(chain) == 1
        assert chain[0][2] == 301

    def test_redirect_missing_location_returns_error(self):
        redirect = make_response(301, headers={}, url="http://example.com")
        with patch("cors_compliance.requests.request", return_value=redirect):
            _, _, err = _follow_to_final("GET", "http://example.com", {}, 10)
        assert err is not None
        assert "Location" in err

    def test_redirect_loop_returns_error(self):
        redirect = make_redirect_response(301, "http://example.com", "http://example.com")
        with patch("cors_compliance.requests.request", return_value=redirect):
            _, _, err = _follow_to_final("GET", "http://example.com", {}, 10)
        assert err is not None
        assert "loop" in err.lower()

    def test_request_error_propagates(self):
        import requests as req
        with patch("cors_compliance.requests.request", side_effect=req.exceptions.ConnectionError("refused")):
            _, _, err = _follow_to_final("GET", "https://example.com", {}, 10)
        assert err is not None
        assert "Connection error" in err


# ---------------------------------------------------------------------------
# run_allow_origin_test
# ---------------------------------------------------------------------------

class TestRunAllowOriginTest:
    def test_wildcard_origin_passes(self):
        resp = make_response(200, headers={"access-control-allow-origin": "*"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", "*", "https://vliz.be", 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_wildcard_origin_fails_when_header_missing(self):
        resp = make_response(200, headers={})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", "*", "https://vliz.be", 10)
        assert result["failure_message"] is not None
        assert result["error"] is None

    def test_wildcard_origin_fails_when_specific_origin_returned(self):
        resp = make_response(200, headers={"access-control-allow-origin": "https://other.com"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", "*", "https://vliz.be", 10)
        assert result["failure_message"] is not None

    def test_specific_origin_passes_when_reflected(self):
        resp = make_response(200, headers={"access-control-allow-origin": "https://vliz.be"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", "https://vliz.be", "https://vliz.be", 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_specific_origin_fails_when_not_reflected(self):
        resp = make_response(200, headers={"access-control-allow-origin": "*"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", "https://vliz.be", "https://vliz.be", 10)
        assert result["failure_message"] is not None

    def test_request_error_sets_error_not_failure(self):
        with patch("cors_compliance._follow_to_final", return_value=(None, [], "Connection refused")):
            result = run_allow_origin_test("https://example.com", "*", "https://vliz.be", 10)
        assert result["error"] is not None
        assert result["failure_message"] is None

    def test_case_name_contains_url_and_origin(self):
        resp = make_response(200, headers={"access-control-allow-origin": "*"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", "*", "https://vliz.be", 10)
        assert "https://example.com" in result["case_name"]
        assert "*" in result["case_name"]

    # Lenient mode tests (origin=None)
    def test_lenient_passes_when_wildcard_returned(self):
        resp = make_response(200, headers={"access-control-allow-origin": "*"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", None, "https://vliz.be", 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_lenient_passes_when_probe_origin_reflected(self):
        resp = make_response(200, headers={"access-control-allow-origin": "https://vliz.be"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", None, "https://vliz.be", 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_lenient_fails_when_header_missing(self):
        resp = make_response(200, headers={})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", None, "https://vliz.be", 10)
        assert result["failure_message"] is not None

    def test_lenient_fails_when_unrecognised_origin_returned(self):
        resp = make_response(200, headers={"access-control-allow-origin": "https://other.com"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", None, "https://vliz.be", 10)
        assert result["failure_message"] is not None

    def test_lenient_case_name_contains_lenient_label(self):
        resp = make_response(200, headers={"access-control-allow-origin": "*"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_origin_test("https://example.com", None, "https://vliz.be", 10)
        assert "lenient" in result["case_name"]


# ---------------------------------------------------------------------------
# run_allow_methods_test
# ---------------------------------------------------------------------------

class TestRunAllowMethodsTest:
    def test_passes_when_all_methods_present(self):
        resp = make_response(200, headers={"access-control-allow-methods": "GET, HEAD, OPTIONS, POST"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_methods_test("https://example.com", ["GET", "HEAD", "OPTIONS"], 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_passes_with_exact_match(self):
        resp = make_response(200, headers={"access-control-allow-methods": "GET, HEAD, OPTIONS"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_methods_test("https://example.com", ["GET", "HEAD", "OPTIONS"], 10)
        assert result["failure_message"] is None

    def test_fails_when_method_missing(self):
        resp = make_response(200, headers={"access-control-allow-methods": "GET, HEAD"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_methods_test("https://example.com", ["GET", "HEAD", "OPTIONS"], 10)
        assert result["failure_message"] is not None
        assert "OPTIONS" in result["failure_text"]

    def test_fails_when_header_missing(self):
        resp = make_response(200, headers={})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_methods_test("https://example.com", ["GET"], 10)
        assert result["failure_message"] is not None
        assert "missing" in result["failure_message"].lower()

    def test_comparison_is_case_insensitive(self):
        resp = make_response(200, headers={"access-control-allow-methods": "get, head, options"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_methods_test("https://example.com", ["GET", "HEAD", "OPTIONS"], 10)
        assert result["failure_message"] is None

    def test_request_error_sets_error_not_failure(self):
        with patch("cors_compliance._follow_to_final", return_value=(None, [], "Timeout")):
            result = run_allow_methods_test("https://example.com", ["GET"], 10)
        assert result["error"] is not None
        assert result["failure_message"] is None


# ---------------------------------------------------------------------------
# run_allow_headers_test
# ---------------------------------------------------------------------------

class TestRunAllowHeadersTest:
    def test_passes_when_all_headers_present(self):
        resp = make_response(200, headers={"access-control-allow-headers": "Accept, X-Custom-Header, Authorization"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_headers_test("https://example.com", ["Accept", "X-Custom-Header"], 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_fails_when_header_missing(self):
        resp = make_response(200, headers={"access-control-allow-headers": "Accept"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_headers_test("https://example.com", ["Accept", "X-Custom-Header"], 10)
        assert result["failure_message"] is not None
        assert "x-custom-header" in result["failure_text"].lower()

    def test_fails_when_header_absent(self):
        resp = make_response(200, headers={})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_headers_test("https://example.com", ["Accept"], 10)
        assert result["failure_message"] is not None

    def test_comparison_is_case_insensitive(self):
        resp = make_response(200, headers={"access-control-allow-headers": "accept, x-custom-header"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_allow_headers_test("https://example.com", ["Accept", "X-Custom-Header"], 10)
        assert result["failure_message"] is None

    def test_request_error_sets_error_not_failure(self):
        with patch("cors_compliance._follow_to_final", return_value=(None, [], "Connection refused")):
            result = run_allow_headers_test("https://example.com", ["Accept"], 10)
        assert result["error"] is not None
        assert result["failure_message"] is None


# ---------------------------------------------------------------------------
# run_expose_headers_test
# ---------------------------------------------------------------------------

class TestRunExposeHeadersTest:
    def test_passes_when_all_headers_exposed(self):
        resp = make_response(200, headers={"access-control-expose-headers": "Content-Type, Link, X-Extra"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_expose_headers_test("https://example.com", ["Content-Type", "Link"], "https://vliz.be", 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_fails_when_header_missing_from_exposed(self):
        resp = make_response(200, headers={"access-control-expose-headers": "Content-Type"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_expose_headers_test("https://example.com", ["Content-Type", "Link"], "https://vliz.be", 10)
        assert result["failure_message"] is not None
        assert "link" in result["failure_text"].lower()

    def test_fails_when_header_absent(self):
        resp = make_response(200, headers={})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_expose_headers_test("https://example.com", ["Content-Type"], "https://vliz.be", 10)
        assert result["failure_message"] is not None

    def test_comparison_is_case_insensitive(self):
        resp = make_response(200, headers={"access-control-expose-headers": "content-type, link"})
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_expose_headers_test("https://example.com", ["Content-Type", "Link"], "https://vliz.be", 10)
        assert result["failure_message"] is None

    def test_request_error_sets_error_not_failure(self):
        with patch("cors_compliance._follow_to_final", return_value=(None, [], "SSL error")):
            result = run_expose_headers_test("https://example.com", ["Content-Type"], "https://vliz.be", 10)
        assert result["error"] is not None
        assert result["failure_message"] is None


# ---------------------------------------------------------------------------
# run_https_redirect_test
# ---------------------------------------------------------------------------

class TestRunHttpsRedirectTest:
    def test_passes_when_redirect_and_cors_header_present(self):
        resp = make_response(200, headers={"access-control-allow-origin": "*"}, url="https://example.com")
        chain = [("http://example.com", "https://example.com", 301)]
        with patch("cors_compliance._follow_to_final", return_value=(resp, chain, None)):
            result = run_https_redirect_test("https://example.com", "https://vliz.be", "*", 10)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_fails_when_no_http_to_https_redirect(self):
        resp = make_response(200, headers={"access-control-allow-origin": "*"}, url="http://example.com")
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            result = run_https_redirect_test("https://example.com", "https://vliz.be", "*", 10)
        assert result["failure_message"] is not None
        assert "redirect" in result["failure_message"].lower()

    def test_fails_when_cors_header_lost_after_redirect(self):
        resp = make_response(200, headers={}, url="https://example.com")
        chain = [("http://example.com", "https://example.com", 301)]
        with patch("cors_compliance._follow_to_final", return_value=(resp, chain, None)):
            result = run_https_redirect_test("https://example.com", "https://vliz.be", "*", 10)
        assert result["failure_message"] is not None
        assert "lost" in result["failure_message"].lower()

    def test_fails_when_cors_header_incorrect_after_redirect(self):
        resp = make_response(200, headers={"access-control-allow-origin": "https://other.com"}, url="https://example.com")
        chain = [("http://example.com", "https://example.com", 301)]
        with patch("cors_compliance._follow_to_final", return_value=(resp, chain, None)):
            result = run_https_redirect_test("https://example.com", "https://vliz.be", "*", 10)
        assert result["failure_message"] is not None

    def test_specific_origin_reflected_after_redirect_passes(self):
        resp = make_response(200, headers={"access-control-allow-origin": "https://vliz.be"}, url="https://example.com")
        chain = [("http://example.com", "https://example.com", 301)]
        with patch("cors_compliance._follow_to_final", return_value=(resp, chain, None)):
            result = run_https_redirect_test("https://example.com", "https://vliz.be", "https://vliz.be", 10)
        assert result["failure_message"] is None

    def test_http_url_is_derived_from_https_url(self):
        captured = {}
        def fake_follow(method, url, headers, timeout):
            captured["url"] = url
            resp = make_response(200, headers={"access-control-allow-origin": "*"}, url="https://example.com")
            chain = [("http://example.com", "https://example.com", 301)]
            return resp, chain, None
        with patch("cors_compliance._follow_to_final", side_effect=fake_follow):
            run_https_redirect_test("https://example.com", "https://vliz.be", "*", 10)
        assert captured["url"].startswith("http://")

    def test_request_error_sets_error_not_failure(self):
        with patch("cors_compliance._follow_to_final", return_value=(None, [], "Connection refused")):
            result = run_https_redirect_test("https://example.com", "https://vliz.be", "*", 10)
        assert result["error"] is not None
        assert result["failure_message"] is None


# ---------------------------------------------------------------------------
# run_tests_for_url
# ---------------------------------------------------------------------------

class TestRunTestsForUrl:
    def _mock_passing_response(self, origin="*"):
        return make_response(200, headers={
            "access-control-allow-origin": origin,
            "access-control-allow-methods": "GET, HEAD, OPTIONS",
            "access-control-allow-headers": "Accept",
            "access-control-expose-headers": "Content-Type, Link",
        })

    def test_produces_four_results_without_redirect(self):
        resp = self._mock_passing_response()
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            # origins=None (lenient) → one origin test case
            results = run_tests_for_url("https://example.com", _config(origins=None, https_redirect=False))
        assert len(results) == 4

    def test_produces_five_results_with_redirect(self):
        resp = self._mock_passing_response()
        chain = [("http://example.com", "https://example.com", 301)]
        with patch("cors_compliance._follow_to_final", return_value=(resp, chain, None)):
            results = run_tests_for_url("https://example.com", _config(https_redirect=True))
        assert len(results) == 5

    def test_produces_one_origin_result_per_origin(self):
        resp = self._mock_passing_response("https://vliz.be")
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(origins=["https://vliz.be", "https://github.com"])
            )
        origin_results = [r for r in results if "access_control_allow_origin" in r["case_name"]]
        assert len(origin_results) == 2

    def test_all_case_names_contain_url(self):
        resp = self._mock_passing_response()
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            results = run_tests_for_url("https://example.com", _config())
        assert all("https://example.com" in r["case_name"] for r in results)

    def test_skips_when_probe_origin_matches_url_origin(self):
        results = run_tests_for_url(
            "https://example.com",
            _config(probe_origin="https://example.com")
        )
        assert len(results) == 1
        assert results[0]["skipped"] is True
        assert "probe-origin" in results[0]["skipped_message"].lower()

    def test_does_not_skip_when_probe_origin_differs_by_scheme(self):
        """http://example.com vs https://example.com are different origins."""
        resp = self._mock_passing_response()
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(probe_origin="http://example.com")
            )
        assert not any(r["skipped"] for r in results)

    def test_does_not_skip_when_probe_origin_differs_by_port(self):
        """https://example.com:8443 vs https://example.com are different origins."""
        resp = self._mock_passing_response()
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(probe_origin="https://example.com:8443")
            )
        assert not any(r["skipped"] for r in results)

    def test_skips_when_probe_origin_matches_url_with_explicit_default_port(self):
        """https://example.com:443 and https://example.com are the same origin."""
        results = run_tests_for_url(
            "https://example.com",
            _config(probe_origin="https://example.com:443")
        )
        assert len(results) == 1
        assert results[0]["skipped"] is True

    def test_does_not_skip_when_probe_origin_differs_from_url(self):
        resp = self._mock_passing_response()
        with patch("cors_compliance._follow_to_final", return_value=(resp, [], None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(probe_origin="https://vliz.be")
            )
        assert not any(r["skipped"] for r in results)


# ---------------------------------------------------------------------------
# skipped_test
# ---------------------------------------------------------------------------

class TestSkippedTest:
    def test_returns_correct_structure(self):
        result = skipped_test("cors_compliance", "No URL configured")
        assert result["skipped"] is True
        assert result["skipped_message"] == "No URL configured"
        assert result["failure_message"] is None
        assert result["error"] is None
        assert result["duration"] == 0.0


# ---------------------------------------------------------------------------
# create_junit_report
# ---------------------------------------------------------------------------

class TestCreateJunitReport:
    def _result(self, name="access_control_allow_origin [https://example.com] [*]",
                failure=False, skipped=False, error=False):
        return {
            "case_name": name,
            "duration": 0.5,
            "error": "some error" if error else None,
            "failure_message": "fail msg" if failure else None,
            "failure_text": "fail detail" if failure else None,
            "properties": {"urls": "https://example.com", "hostnames": "example.com"},
            "skipped": skipped,
            "skipped_message": "reason" if skipped else "",
            "stdout": "some output",
            "stderr": "some err" if (failure or error) else "",
        }

    def test_creates_xml_file(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, {"urls", "hostnames"}, "prov")
        assert os.path.exists(out)

    def test_failure_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(failure=True)], out, set(), "prov")
        assert "failure" in open(out).read().lower()

    def test_skipped_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(skipped=True)], out, set(), "prov")
        assert "skipped" in open(out).read().lower()

    def test_error_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(error=True)], out, set(), "prov")
        assert "error" in open(out).read().lower()

    def test_provenance_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "my-provenance-value")
        assert "my-provenance-value" in open(out).read()

    def test_timeout_property_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov",
                            suite_properties={"timeout": 30})
        content = open(out).read()
        assert 'name="timeout"' in content
        assert '"30"' in content

    def test_timeout_absent_when_suite_properties_not_passed(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov")
        assert 'name="timeout"' not in open(out).read()

    def test_append_property_urls_deduplicated(self, tmp_path):
        """Multiple results for the same URL should produce a single entry, not duplicates."""
        out = str(tmp_path / "report.xml")
        results = [self._result("t1"), self._result("t2"), self._result("t3")]
        create_junit_report("suite", results, out, {"urls", "hostnames"}, "prov")
        content = open(out).read()
        assert 'name="urls"' in content
        assert "https://example.com, https://example.com" not in content
        assert content.count("https://example.com") >= 1

    def test_append_property_urls_multiple_distinct_values(self, tmp_path):
        """Two different URLs should both appear in the property."""
        out = str(tmp_path / "report.xml")
        r1 = dict(self._result("t1"), properties={"urls": "https://a.com", "hostnames": "a.com"})
        r2 = dict(self._result("t2"), properties={"urls": "https://b.com", "hostnames": "b.com"})
        create_junit_report("suite", [r1, r2], out, {"urls", "hostnames"}, "prov")
        content = open(out).read()
        assert "https://a.com" in content
        assert "https://b.com" in content

    def test_suite_time_equals_sum_of_durations(self, tmp_path):
        from junitparser import JUnitXml as JX
        out = str(tmp_path / "report.xml")
        results = [self._result("t1"), self._result("t2")]
        create_junit_report("suite", results, out, set(), "prov")
        xml = JX.fromfile(out)
        for suite in xml:
            assert abs(suite.time - 1.0) < 0.001

    def test_empty_results_still_creates_file(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [], out, set(), "prov")
        assert os.path.exists(out)

    def test_config_properties_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        props = {
            "timeout": 30,
            "origins": ["*"],
            "allow_methods": ["GET", "HEAD", "OPTIONS"],
            "allow_headers": ["Accept"],
            "expose_headers": ["Content-Type", "Link"],
            "https_redirect": False,
            "probe_origin": "https://vliz.be",
        }
        create_junit_report("suite", [self._result()], out, set(), "prov", suite_properties=props)
        content = open(out).read()
        assert 'name="access-control-allow-origin"' in content
        assert 'name="access-control-allow-methods"' in content
        assert 'name="access-control-allow-headers"' in content
        assert 'name="access-control-expose-headers"' in content
        assert 'name="https-redirect"' in content
        assert 'name="probe-origin"' in content

    def test_config_properties_absent_when_suite_properties_not_passed(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov")
        content = open(out).read()
        assert 'name="access-control-allow-origin"' not in content
        assert 'name="access-control-allow-methods"' not in content
        assert 'name="https-redirect"' not in content
        assert 'name="probe-origin"' not in content

    def test_https_redirect_false_written_as_lowercase_string(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov",
                            suite_properties={"https_redirect": False})
        assert '"false"' in open(out).read()

    def test_https_redirect_true_written_as_lowercase_string(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov",
                            suite_properties={"https_redirect": True})
        assert '"true"' in open(out).read()