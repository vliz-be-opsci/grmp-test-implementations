"""
Unit tests for content_negotiation.py

Run with (from content-negotiation/ root):
    pip install pytest requests junitparser rdflib
    pytest tests/test_content_negotiation.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from unittest.mock import patch, MagicMock

from content_negotiation import (
    parse_config,
    _parse_accept_header,
    _is_complex_accept_header,
    _extract_response_content_type,
    _check_body_conformity,
    run_content_negotiation_test,
    run_body_conformity_test,
    run_tests_for_url,
    skipped_test,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_response(status_code=200, content_type="text/turtle", body=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {"content-type": content_type} if content_type is not None else {}
    resp.text = body
    return resp


def _config(**overrides):
    base = {
        "timeout": 10,
        "accept_headers": ["text/turtle"],
        "check_body_conformity": None,
        "provenance": "test",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# parse_config
# ---------------------------------------------------------------------------

class TestParseConfig:
    ENV_KEYS = [
        "TEST_URLS",
        "TEST_ACCEPT-HEADERS",
        "TEST_CHECK-RESPONSE-BODY-CONFORMITY",
        "TEST_TIMEOUT",
        "SPECIAL_SOURCE_FILE",
        "SPECIAL_CREATE_ISSUE",
    ]

    def _clean(self, monkeypatch):
        for k in self.ENV_KEYS:
            monkeypatch.delenv(k, raising=False)

    def test_defaults(self, monkeypatch):
        self._clean(monkeypatch)
        config = parse_config()
        assert config["urls"] == []
        assert config["accept_headers"] is None
        assert config["check_body_conformity"] is None
        assert config["timeout"] == 30
        assert config["provenance"] == "unknown"
        assert config["create_issue"] is False

    def test_custom_urls(self, monkeypatch):
        monkeypatch.setenv("TEST_URLS", "['https://example.com']")
        assert parse_config()["urls"] == ["https://example.com"]

    def test_custom_accept_headers(self, monkeypatch):
        monkeypatch.setenv("TEST_ACCEPT-HEADERS", "['text/turtle', 'application/ld+json']")
        assert parse_config()["accept_headers"] == ["text/turtle", "application/ld+json"]

    def test_bare_accept_header(self, monkeypatch):
        monkeypatch.setenv("TEST_ACCEPT-HEADERS", "text/turtle")
        assert parse_config()["accept_headers"] == ["text/turtle"]

    def test_check_body_conformity_true(self, monkeypatch):
        monkeypatch.setenv("TEST_CHECK-RESPONSE-BODY-CONFORMITY", "true")
        assert parse_config()["check_body_conformity"] is True

    def test_check_body_conformity_false(self, monkeypatch):
        monkeypatch.setenv("TEST_CHECK-RESPONSE-BODY-CONFORMITY", "false")
        assert parse_config()["check_body_conformity"] is False

    def test_check_body_conformity_absent(self, monkeypatch):
        monkeypatch.delenv("TEST_CHECK-RESPONSE-BODY-CONFORMITY", raising=False)
        assert parse_config()["check_body_conformity"] is None

    def test_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "15")
        assert parse_config()["timeout"] == 15

    def test_invalid_timeout_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "bad")
        assert parse_config()["timeout"] == 30

    def test_zero_timeout_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "0")
        assert parse_config()["timeout"] == 30

    def test_provenance(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "my-config.yaml")
        assert parse_config()["provenance"] == "my-config.yaml"

    def test_create_issue_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv("SPECIAL_CREATE_ISSUE", raising=False)
        assert parse_config()["create_issue"] is False

    def test_create_issue_true_when_set(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_CREATE_ISSUE", "true")
        assert parse_config()["create_issue"] is True


# ---------------------------------------------------------------------------
# _parse_accept_header
# ---------------------------------------------------------------------------

class TestParseAcceptHeader:
    def test_simple_type(self):
        assert _parse_accept_header("text/turtle") == ["text/turtle"]

    def test_simple_type_with_charset(self):
        assert _parse_accept_header("text/turtle;charset=utf-8") == ["text/turtle"]

    def test_complex_header(self):
        result = _parse_accept_header(
            "application/ld+json, application/trig;q=0.98, text/turtle;q=0.95"
        )
        assert result == ["application/ld+json", "application/trig", "text/turtle"]

    def test_full_complex_header(self):
        result = _parse_accept_header(
            "application/ld+json, application/trig;q=0.98, text/turtle;q=0.95, "
            "application/n-quads;q=0.9, application/n-triples;q=0.9, "
            "application/rdf+xml;q=0.5, text/html;q=0.3, */*;q=0.1"
        )
        assert "application/ld+json" in result
        assert "text/turtle" in result
        assert "*/*" in result
        assert len(result) == 8

    def test_strips_whitespace(self):
        assert _parse_accept_header("  text/turtle  ") == ["text/turtle"]

    def test_lowercases_types(self):
        assert _parse_accept_header("Text/Turtle") == ["text/turtle"]

    def test_wildcard(self):
        assert _parse_accept_header("*/*") == ["*/*"]


# ---------------------------------------------------------------------------
# _is_complex_accept_header
# ---------------------------------------------------------------------------

class TestIsComplexAcceptHeader:
    def test_simple_is_not_complex(self):
        assert _is_complex_accept_header("text/turtle") is False

    def test_with_qvalue_is_complex(self):
        assert _is_complex_accept_header("text/turtle;q=0.9") is True

    def test_multiple_types_is_complex(self):
        assert _is_complex_accept_header("text/turtle, application/ld+json") is True

    def test_full_complex_header_is_complex(self):
        assert _is_complex_accept_header(
            "application/ld+json, text/turtle;q=0.9, */*;q=0.1"
        ) is True


# ---------------------------------------------------------------------------
# _extract_response_content_type
# ---------------------------------------------------------------------------

class TestExtractResponseContentType:
    def test_simple_content_type(self):
        resp = make_response(content_type="text/turtle")
        assert _extract_response_content_type(resp) == "text/turtle"

    def test_strips_charset(self):
        resp = make_response(content_type="text/turtle; charset=utf-8")
        assert _extract_response_content_type(resp) == "text/turtle"

    def test_lowercases(self):
        resp = make_response(content_type="Text/Turtle")
        assert _extract_response_content_type(resp) == "text/turtle"

    def test_absent_content_type(self):
        resp = make_response(content_type=None)
        assert _extract_response_content_type(resp) == ""


# ---------------------------------------------------------------------------
# _check_body_conformity
# ---------------------------------------------------------------------------

class TestCheckBodyConformity:
    def test_non_rdf_type_is_skipped(self):
        skipped, failure_msg, _ = _check_body_conformity("<html/>", "text/html")
        assert skipped is True
        assert failure_msg is None

    def test_unknown_type_is_skipped(self):
        skipped, failure_msg, _ = _check_body_conformity("body", "application/octet-stream")
        assert skipped is True

    def test_valid_turtle_passes(self):
        turtle = "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
        skipped, failure_msg, _ = _check_body_conformity(turtle, "text/turtle")
        assert skipped is False
        assert failure_msg is None

    def test_invalid_turtle_fails(self):
        skipped, failure_msg, failure_text = _check_body_conformity(
            "this is not turtle !!!@@@", "text/turtle"
        )
        assert skipped is False
        assert failure_msg is not None
        assert "text/turtle" in failure_msg

    def test_valid_ntriples_passes(self):
        nt = "<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n"
        skipped, failure_msg, _ = _check_body_conformity(nt, "application/n-triples")
        assert skipped is False
        assert failure_msg is None

    def test_invalid_json_ld_fails(self):
        skipped, failure_msg, _ = _check_body_conformity(
            "not json at all", "application/ld+json"
        )
        assert skipped is False
        assert failure_msg is not None


# ---------------------------------------------------------------------------
# run_content_negotiation_test
# ---------------------------------------------------------------------------

class TestRunContentNegotiationTest:
    """run_content_negotiation_test returns (result, response, matched_content_type)."""

    def _run(self, url, accept_header, timeout=10, response=None, req_err=None):
        if response is None and req_err is None:
            response = make_response(200, content_type="text/turtle")
        with patch("content_negotiation._request", return_value=(response, req_err)):
            return run_content_negotiation_test(url, accept_header, timeout)

    def test_passes_simple_type(self):
        result, _, matched = self._run("https://example.com", "text/turtle")
        assert result["failure_message"] is None
        assert result["error"] is None
        assert matched == "text/turtle"

    def test_fails_when_status_not_2xx(self):
        result, _, matched = self._run(
            "https://example.com", "text/turtle",
            response=make_response(404, content_type="text/turtle")
        )
        assert result["failure_message"] is not None
        assert "404" in result["failure_message"]
        assert matched is None

    def test_fails_when_content_type_missing(self):
        result, _, matched = self._run(
            "https://example.com", "text/turtle",
            response=make_response(200, content_type=None)
        )
        assert result["failure_message"] is not None
        assert "Content-Type" in result["failure_message"]
        assert matched is None

    def test_fails_when_simple_type_does_not_match(self):
        result, _, matched = self._run(
            "https://example.com", "text/turtle",
            response=make_response(200, content_type="text/html")
        )
        assert result["failure_message"] is not None
        assert "text/html" in result["failure_text"]
        assert matched is None

    def test_passes_complex_header_when_type_in_list(self):
        accept = "application/ld+json, text/turtle;q=0.9, */*;q=0.1"
        result, _, matched = self._run(
            "https://example.com", accept,
            response=make_response(200, content_type="text/turtle")
        )
        assert result["failure_message"] is None
        assert matched == "text/turtle"

    def test_fails_complex_header_when_type_not_in_list(self):
        accept = "application/ld+json, text/turtle;q=0.9"
        result, _, matched = self._run(
            "https://example.com", accept,
            response=make_response(200, content_type="text/html")
        )
        assert result["failure_message"] is not None
        assert matched is None

    def test_passes_wildcard_only_accept_with_any_content_type(self):
        result, _, matched = self._run(
            "https://example.com", "*/*",
            response=make_response(200, content_type="text/html")
        )
        assert result["failure_message"] is None
        assert matched == "text/html"

    def test_complex_header_with_only_wildcard_passes_any_type(self):
        result, _, matched = self._run(
            "https://example.com", "*/*;q=0.1",
            response=make_response(200, content_type="text/html")
        )
        assert result["failure_message"] is None

    def test_request_error_sets_error_not_failure(self):
        result, response, matched = self._run(
            "https://example.com", "text/turtle", req_err="Connection refused"
        )
        assert result["error"] is not None
        assert result["failure_message"] is None
        assert response is None
        assert matched is None

    def test_case_name_contains_url_and_accept_header(self):
        result, _, _ = self._run("https://example.com", "text/turtle")
        assert "https://example.com" in result["case_name"]
        assert "text/turtle" in result["case_name"]

    def test_content_type_with_charset_still_matches(self):
        result, _, matched = self._run(
            "https://example.com", "text/turtle",
            response=make_response(200, content_type="text/turtle; charset=utf-8")
        )
        assert result["failure_message"] is None
        assert matched == "text/turtle"


# ---------------------------------------------------------------------------
# run_body_conformity_test
# ---------------------------------------------------------------------------

class TestRunBodyConformityTest:
    TURTLE = "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."

    def test_passes_valid_turtle_body(self):
        resp = make_response(200, content_type="text/turtle", body=self.TURTLE)
        result = run_body_conformity_test("https://example.com", "text/turtle", resp, "text/turtle")
        assert result["failure_message"] is None
        assert result["skipped"] is False

    def test_fails_invalid_turtle_body(self):
        resp = make_response(200, content_type="text/turtle", body="not valid turtle !!!")
        result = run_body_conformity_test("https://example.com", "text/turtle", resp, "text/turtle")
        assert result["failure_message"] is not None
        assert result["skipped"] is False

    def test_skipped_when_matched_content_type_is_none(self):
        result = run_body_conformity_test("https://example.com", "text/turtle", None, None)
        assert result["skipped"] is True
        assert "content negotiation test" in result["skipped_message"].lower()

    def test_skipped_for_non_rdf_content_type(self):
        resp = make_response(200, content_type="text/html", body="<html/>")
        result = run_body_conformity_test("https://example.com", "*/*", resp, "text/html")
        assert result["skipped"] is True
        assert "text/html" in result["skipped_message"]

    def test_case_name_contains_url_and_accept_header(self):
        resp = make_response(200, content_type="text/turtle", body=self.TURTLE)
        result = run_body_conformity_test("https://example.com", "text/turtle", resp, "text/turtle")
        assert "https://example.com" in result["case_name"]
        assert "text/turtle" in result["case_name"]
        assert "body_conformity" in result["case_name"]


# ---------------------------------------------------------------------------
# run_tests_for_url
# ---------------------------------------------------------------------------

class TestRunTestsForUrl:
    def test_produces_one_cn_result_per_accept_header_without_body_conformity(self):
        resp = make_response(200, content_type="text/turtle")
        with patch("content_negotiation._request", return_value=(resp, None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(accept_headers=["text/turtle", "application/ld+json"],
                        check_body_conformity=None)
            )
        assert len(results) == 2
        assert all("content_negotiation" in r["case_name"] for r in results)

    def test_produces_cn_and_body_result_per_accept_header_with_body_conformity(self):
        turtle = "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."
        resp = make_response(200, content_type="text/turtle", body=turtle)
        with patch("content_negotiation._request", return_value=(resp, None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(accept_headers=["text/turtle", "text/turtle"],
                        check_body_conformity=True)
            )
        assert len(results) == 4
        cn_results = [r for r in results if "content_negotiation" in r["case_name"]]
        body_results = [r for r in results if "body_conformity" in r["case_name"]]
        assert len(cn_results) == 2
        assert len(body_results) == 2

    def test_body_conformity_skipped_when_cn_failed(self):
        resp = make_response(200, content_type="text/html")
        with patch("content_negotiation._request", return_value=(resp, None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(accept_headers=["text/turtle"], check_body_conformity=True)
            )
        body_result = next(r for r in results if "body_conformity" in r["case_name"])
        assert body_result["skipped"] is True

    def test_all_case_names_contain_url(self):
        resp = make_response(200, content_type="text/turtle")
        with patch("content_negotiation._request", return_value=(resp, None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(accept_headers=["text/turtle", "application/ld+json"])
            )
        assert all("https://example.com" in r["case_name"] for r in results)

    def test_single_accept_header_produces_one_result_without_body_conformity(self):
        resp = make_response(200, content_type="text/turtle")
        with patch("content_negotiation._request", return_value=(resp, None)):
            results = run_tests_for_url(
                "https://example.com",
                _config(accept_headers=["text/turtle"], check_body_conformity=None)
            )
        assert len(results) == 1