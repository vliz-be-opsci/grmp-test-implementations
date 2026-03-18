#!/usr/bin/env python3
"""
Unit tests for resource_availability.py

Run with (from resource-availability/ root):
    pip install pytest junitparser requests
    pytest tests/test_resource_availability.py -v
"""

import socket
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from resource_availability import (
    check_dns,
    check_url,
    run_dns_test,
    run_availability_test,
    run_tests_for_url,
    skipped_test,
    parse_config,
    create_junit_report,
    _parse_list_env,
    _parse_int_env,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_response(status_code, headers=None, url="https://example.com"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.url = url
    return resp


# ---------------------------------------------------------------------------
# check_dns
# ---------------------------------------------------------------------------

class TestCheckDns:
    def test_successful_resolution(self):
        with patch("socket.gethostbyname", return_value="93.184.216.34"):
            ip, error = check_dns("example.com")
        assert ip == "93.184.216.34"
        assert error is None

    def test_failed_resolution(self):
        with patch("socket.gethostbyname", side_effect=socket.gaierror("Name or service not known")):
            ip, error = check_dns("nonexistent.invalid")
        assert ip is None
        assert "Name or service not known" in error

    def test_none_hostname_returns_error(self):
        ip, error = check_dns(None)
        assert ip is None
        assert error == "Could not extract hostname from URL"


# ---------------------------------------------------------------------------
# check_url
# ---------------------------------------------------------------------------

class TestCheckUrl:
    def test_200_response(self):
        with patch("requests.Session.get", return_value=make_response(200)):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=10, max_redirects=0
            )
        assert status == 200
        assert error is None
        assert crossed is False

    def test_timeout_returns_error(self):
        import requests as req
        with patch("requests.Session.get", side_effect=req.exceptions.Timeout):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=5, max_redirects=0
            )
        assert status is None
        assert "timed out" in error

    def test_connection_error(self):
        import requests as req
        with patch("requests.Session.get", side_effect=req.exceptions.ConnectionError("refused")):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=5, max_redirects=0
            )
        assert status is None
        assert error is not None

    def test_redirect_within_same_scheme_is_followed(self):
        redirect_resp = make_response(301, headers={"Location": "https://example.com/new"})
        final_resp = make_response(200)
        with patch("requests.Session.get", side_effect=[redirect_resp, final_resp]):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=10, max_redirects=5
            )
        assert status == 200
        assert error is None
        assert crossed is False

    def test_redirect_limit_exceeded_returns_error(self):
        redirect_resp = make_response(301, headers={"Location": "https://example.com/loop"})
        with patch("requests.Session.get", return_value=redirect_resp):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=10, max_redirects=0
            )
        assert "Redirect limit reached" in error

    def test_http_to_https_redirect_crosses_boundary(self):
        redirect_resp = make_response(301, headers={"Location": "https://example.com/"})
        with patch("requests.Session.get", return_value=redirect_resp):
            status, final_url, elapsed, error, crossed = check_url(
                "http://example.com", timeout=10, max_redirects=5
            )
        assert crossed is True
        assert error is None
        assert final_url.startswith("https://")

    def test_https_to_http_redirect_crosses_boundary(self):
        redirect_resp = make_response(301, headers={"Location": "http://example.com/"})
        with patch("requests.Session.get", return_value=redirect_resp):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=10, max_redirects=5
            )
        assert crossed is True
        assert final_url.startswith("http://")

    def test_redirect_missing_location_header_returns_error(self):
        with patch("requests.Session.get", return_value=make_response(301, headers={})):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=10, max_redirects=5
            )
        assert error is not None
        assert "no Location header" in error

    def test_500_returns_unexpected_status_error(self):
        with patch("requests.Session.get", return_value=make_response(500)):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com", timeout=10, max_redirects=0
            )
        assert status == 500
        assert "Unexpected status code" in error

    def test_404_returns_error(self):
        with patch("requests.Session.get", return_value=make_response(404)):
            status, final_url, elapsed, error, crossed = check_url(
                "https://example.com/missing", timeout=10, max_redirects=0
            )
        assert status == 404
        assert error is not None

    def test_elapsed_is_non_negative(self):
        with patch("requests.Session.get", return_value=make_response(200)):
            _, _, elapsed, _, _ = check_url("https://example.com", timeout=10, max_redirects=0)
        assert elapsed >= 0


# ---------------------------------------------------------------------------
# skipped_test
# ---------------------------------------------------------------------------

class TestSkippedTest:
    def test_returns_correct_structure(self):
        result = skipped_test("my_test [http://x.com]", "No URL configured")
        assert result["skipped"] is True
        assert result["skipped_message"] == "No URL configured"
        assert result["case_name"] == "my_test [http://x.com]"
        assert result["failure_message"] is None
        assert result["error"] is None
        assert result["duration"] == 0.0


# ---------------------------------------------------------------------------
# run_dns_test
# ---------------------------------------------------------------------------

class TestRunDnsTest:
    def test_success_has_no_failure(self):
        with patch("resource_availability.check_dns", return_value=("1.2.3.4", None)):
            result = run_dns_test("https://example.com")
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_success_stdout_contains_ip(self):
        with patch("resource_availability.check_dns", return_value=("1.2.3.4", None)):
            result = run_dns_test("https://example.com")
        assert "1.2.3.4" in result["stdout"]

    def test_failure_sets_failure_message(self):
        with patch("resource_availability.check_dns", return_value=(None, "Name not known")):
            result = run_dns_test("https://nonexistent.invalid")
        assert result["failure_message"] is not None
        assert "DNS resolution failed" in result["failure_message"]

    def test_failure_puts_message_in_stdout(self):
        with patch("resource_availability.check_dns", return_value=(None, "Name not known")):
            result = run_dns_test("https://nonexistent.invalid")
        assert "Name not known" in result["stdout"]
        assert result["stderr"] == ""

    def test_properties_contain_hostname(self):
        with patch("resource_availability.check_dns", return_value=("1.2.3.4", None)):
            result = run_dns_test("https://example.com")
        assert result["properties"]["hostnames"] == "example.com"

    def test_properties_contain_url(self):
        with patch("resource_availability.check_dns", return_value=("1.2.3.4", None)):
            result = run_dns_test("https://example.com")
        assert result["properties"]["urls"] == "https://example.com"


# ---------------------------------------------------------------------------
# run_availability_test
# ---------------------------------------------------------------------------

class TestRunAvailabilityTest:
    def test_https_success(self):
        with patch("resource_availability.check_url", return_value=(200, "https://example.com", 0.1, None, False)):
            result = run_availability_test("https://example.com", "https", timeout=10, max_redirects=0)
        assert result["failure_message"] is None
        assert result["error"] is None
        assert "OK" in result["stdout"]

    def test_http_success(self):
        with patch("resource_availability.check_url", return_value=(200, "http://example.com", 0.05, None, False)):
            result = run_availability_test("http://example.com", "http", timeout=10, max_redirects=0)
        assert result["failure_message"] is None

    def test_connection_error_sets_failure(self):
        with patch("resource_availability.check_url", return_value=(None, "https://example.com", 0.5, "Connection refused", False)):
            result = run_availability_test("https://example.com", "https", timeout=10, max_redirects=0)
        assert result["failure_message"] is not None
        assert "Connection refused" in result["failure_text"]

    def test_elapsed_gte_timeout_sets_error(self):
        with patch("resource_availability.check_url", return_value=(None, "https://example.com", 10.0, None, False)):
            result = run_availability_test("https://example.com", "https", timeout=10, max_redirects=0)
        assert result["error"] is not None
        assert "exceeded timeout" in result["error"]

    def test_scheme_boundary_cross_is_not_a_failure(self):
        with patch("resource_availability.check_url", return_value=(301, "https://example.com/", 0.05, None, True)):
            result = run_availability_test("http://example.com", "http", timeout=10, max_redirects=0)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_scheme_boundary_cross_mentioned_in_stdout(self):
        with patch("resource_availability.check_url", return_value=(301, "https://example.com/", 0.05, None, True)):
            result = run_availability_test("http://example.com", "http", timeout=10, max_redirects=0)
        assert "redirects to" in result["stdout"].lower()

    def test_verify_ssl_passed_to_check_url(self):
        captured = {}
        def fake_check_url(url, timeout, max_redirects, verify_ssl):
            captured["verify_ssl"] = verify_ssl
            return 200, url, 0.1, None, False
        with patch("resource_availability.check_url", side_effect=fake_check_url):
            run_availability_test("https://example.com", "https", timeout=10, max_redirects=0, verify_ssl=False)
        assert captured["verify_ssl"] is False

    def test_target_url_uses_specified_scheme(self):
        captured = {}
        def fake_check_url(url, timeout, max_redirects, verify_ssl):
            captured["url"] = url
            return 200, url, 0.1, None, False
        with patch("resource_availability.check_url", side_effect=fake_check_url):
            run_availability_test("https://example.com", "http", timeout=10, max_redirects=0)
        assert captured["url"].startswith("http://")


# ---------------------------------------------------------------------------
# run_tests_for_url
# ---------------------------------------------------------------------------

class TestRunTestsForUrl:
    def _config(self, **overrides):
        cfg = {"timeout": 10, "max_redirects": 0, "verify_ssl": True,
               "check_http": False, "check_https": True}
        cfg.update(overrides)
        return cfg

    def _dns_ok(self, url):
        return {"case_name": f"dns_resolution [{url}]", "duration": 0.05,
                "error": None, "failure_message": None, "failure_text": None,
                "properties": {"urls": url, "hostnames": "example.com"},
                "skipped": False, "skipped_message": "", "stdout": "", "stderr": ""}

    def _dns_fail(self, url):
        return {"case_name": f"dns_resolution [{url}]", "duration": 0.05,
                "error": None, "failure_message": "DNS failed", "failure_text": "err",
                "properties": {"urls": url, "hostnames": "example.com"},
                "skipped": False, "skipped_message": "", "stdout": "", "stderr": ""}

    def _avail_ok(self, url, scheme):
        return {"case_name": f"{scheme}_availability [{url}]", "duration": 0.1,
                "error": None, "failure_message": None, "failure_text": None,
                "properties": {"verify_ssl": "True"},
                "skipped": False, "skipped_message": "", "stdout": "OK", "stderr": ""}

    def test_dns_failure_skips_https(self):
        url = "https://x.com"
        with patch("resource_availability.run_dns_test", return_value=self._dns_fail(url)):
            results = run_tests_for_url(url, self._config())
        skipped = [r for r in results if r["skipped"]]
        assert len(skipped) == 1
        assert "DNS" in skipped[0]["skipped_message"]

    def test_dns_failure_skips_http_when_enabled(self):
        url = "http://x.com"
        with patch("resource_availability.run_dns_test", return_value=self._dns_fail(url)):
            results = run_tests_for_url(url, self._config(check_http=True, check_https=False))
        skipped = [r for r in results if r["skipped"]]
        assert len(skipped) == 1

    def test_dns_success_runs_https(self):
        url = "https://example.com"
        with patch("resource_availability.run_dns_test", return_value=self._dns_ok(url)), \
             patch("resource_availability.run_availability_test", return_value=self._avail_ok(url, "https")):
            results = run_tests_for_url(url, self._config())
        assert len(results) == 2
        assert all(not r["skipped"] for r in results)

    def test_dns_success_runs_http_when_enabled(self):
        url = "http://example.com"
        with patch("resource_availability.run_dns_test", return_value=self._dns_ok(url)), \
             patch("resource_availability.run_availability_test", return_value=self._avail_ok(url, "http")):
            results = run_tests_for_url(url, self._config(check_http=True, check_https=False))
        assert len(results) == 2

    def test_both_protocols_run_when_enabled(self):
        url = "https://example.com"
        with patch("resource_availability.run_dns_test", return_value=self._dns_ok(url)), \
             patch("resource_availability.run_availability_test", return_value=self._avail_ok(url, "https")):
            results = run_tests_for_url(url, self._config(check_http=True, check_https=True))
        assert len(results) == 3  # dns + http + https

    def test_only_dns_when_both_checks_disabled(self):
        url = "https://example.com"
        with patch("resource_availability.run_dns_test", return_value=self._dns_ok(url)):
            results = run_tests_for_url(url, self._config(check_http=False, check_https=False))
        assert len(results) == 1


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

    def test_wraps_quoted_string_in_list(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "'single'")
        assert _parse_list_env("TEST_FOO", []) == ["single"]

    def test_bare_unquoted_string_wrapped_in_list(self, monkeypatch):
        # e.g. TEST_URLS=https://example.com in docker-compose
        monkeypatch.setenv("TEST_FOO", "https://example.com")
        assert _parse_list_env("TEST_FOO", []) == ["https://example.com"]

    def test_syntactically_invalid_value_treated_as_bare_string(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "not valid{{")
        assert _parse_list_env("TEST_FOO", ["default"]) == ["not valid{{"]

    def test_filters_empty_strings(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "['a', '', 'b']")
        assert _parse_list_env("TEST_FOO", []) == ["a", "b"]

    def test_strips_whitespace_from_values(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "['https://a.com', '  https://b.com  ']")
        assert _parse_list_env("TEST_FOO", []) == ["https://a.com", "https://b.com"]

    def test_non_list_type_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_FOO", "42")
        assert _parse_list_env("TEST_FOO", ["default"]) == ["default"]


# ---------------------------------------------------------------------------
# parse_config
# ---------------------------------------------------------------------------

class TestParseConfig:
    ENV_KEYS = ["TEST_URLS", "TEST_TIMEOUT", "TEST_MAX-REDIRECTS",
                "TEST_CHECK-HTTP-AVAILABILITY", "TEST_CHECK-HTTPS-AVAILABILITY",
                "TEST_VERIFY-SSL", "SPECIAL_SOURCE_FILE"]

    def _clean(self, monkeypatch):
        for k in self.ENV_KEYS:
            monkeypatch.delenv(k, raising=False)

    def test_defaults(self, monkeypatch):
        self._clean(monkeypatch)
        config = parse_config()
        assert config["urls"] == []
        assert config["timeout"] == 30
        assert config["max_redirects"] == 0
        assert config["check_http"] is False
        assert config["check_https"] is True
        assert config["verify_ssl"] is True
        assert config["provenance"] == "unknown"

    def test_custom_urls(self, monkeypatch):
        monkeypatch.setenv("TEST_URLS", "['https://example.com']")
        assert parse_config()["urls"] == ["https://example.com"]

    def test_check_http_enabled(self, monkeypatch):
        monkeypatch.setenv("TEST_CHECK-HTTP-AVAILABILITY", "true")
        assert parse_config()["check_http"] is True

    def test_check_https_disabled(self, monkeypatch):
        monkeypatch.setenv("TEST_CHECK-HTTPS-AVAILABILITY", "false")
        assert parse_config()["check_https"] is False

    def test_verify_ssl_disabled(self, monkeypatch):
        monkeypatch.setenv("TEST_VERIFY-SSL", "false")
        assert parse_config()["verify_ssl"] is False

    def test_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "60")
        assert parse_config()["timeout"] == 60

    def test_invalid_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "not-a-number")
        assert parse_config()["timeout"] == 30

    def test_zero_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "0")
        assert parse_config()["timeout"] == 30

    def test_negative_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "-5")
        assert parse_config()["timeout"] == 30

    def test_custom_max_redirects(self, monkeypatch):
        monkeypatch.setenv("TEST_MAX-REDIRECTS", "5")
        assert parse_config()["max_redirects"] == 5

    def test_zero_max_redirects_is_valid(self, monkeypatch):
        monkeypatch.setenv("TEST_MAX-REDIRECTS", "0")
        assert parse_config()["max_redirects"] == 0

    def test_invalid_max_redirects_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_MAX-REDIRECTS", "not-a-number")
        assert parse_config()["max_redirects"] == 0

    def test_negative_max_redirects_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_MAX-REDIRECTS", "-1")
        assert parse_config()["max_redirects"] == 0

    def test_provenance_from_env(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "my-config.yaml")
        assert parse_config()["provenance"] == "my-config.yaml"


# ---------------------------------------------------------------------------
# create_junit_report
# ---------------------------------------------------------------------------

class TestCreateJunitReport:
    def _result(self, name="test_case", failure=False, skipped=False, error=False):
        return {
            "case_name": name, "duration": 0.5,
            "error": "some error" if error else None,
            "failure_message": "fail msg" if failure else None,
            "failure_text": "fail detail" if failure else None,
            "properties": {"urls": "https://example.com", "hostnames": "example.com"},
            "skipped": skipped, "skipped_message": "reason" if skipped else "",
            "stdout": "some output", "stderr": "some err" if error else "",
        }

    def test_creates_xml_file(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("my-suite", [self._result()], out, {"urls", "hostnames"}, "test")
        assert os.path.exists(out)

    def test_failure_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(failure=True)], out, set(), "test")
        assert "failure" in open(out).read().lower()

    def test_skipped_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(skipped=True)], out, set(), "test")
        assert "skipped" in open(out).read().lower()

    def test_error_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(error=True)], out, set(), "test")
        assert "error" in open(out).read().lower()

    def test_stderr_present_in_xml_on_error(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(error=True)], out, set(), "prov")
        assert "some err" in open(out).read()

    def test_stderr_absent_in_xml_on_failure(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(failure=True)], out, set(), "prov")
        assert "some err" not in open(out).read()

    def test_provenance_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "my-provenance-value")
        assert "my-provenance-value" in open(out).read()

    def test_suite_properties_written_to_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        suite_props = {
            "timeout": 60,
            "max_redirects": 3,
            "check_http": True,
            "check_https": False,
            "verify_ssl": False,
        }
        create_junit_report("suite", [self._result()], out, set(), "prov",
                            suite_properties=suite_props)
        xml_content = open(out).read()
        assert 'name="timeout" value="60"' in xml_content
        assert 'name="max-redirects" value="3"' in xml_content
        assert 'name="check-http-availability" value="true"' in xml_content
        assert 'name="check-https-availability" value="false"' in xml_content
        assert 'name="verify-ssl" value="false"' in xml_content

    def test_suite_properties_absent_when_not_passed(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov")
        xml_content = open(out).read()
        assert 'name="timeout"' not in xml_content
        assert 'name="max-redirects"' not in xml_content
        assert 'name="check-http-availability"' not in xml_content
        assert 'name="check-https-availability"' not in xml_content
        assert 'name="verify-ssl"' not in xml_content

    def test_append_property_urls_comma_joined(self, tmp_path):
        out = str(tmp_path / "report.xml")
        results = [self._result("t1"), self._result("t2")]
        create_junit_report("suite", results, out, {"urls", "hostnames"}, "prov")
        content = open(out).read()
        assert 'name="urls"' in content
        assert 'value="https://example.com"' in content

    def test_append_property_urls_deduplicated(self, tmp_path):
        out = str(tmp_path / "report.xml")
        results = [self._result("t1"), self._result("t2")]  # both have same URL
        create_junit_report("suite", results, out, {"urls", "hostnames"}, "prov")
        content = open(out).read()
        # same URL should appear only once, not twice
        assert content.count("https://example.com") == 1

    def test_append_property_hostnames_comma_joined(self, tmp_path):
        out = str(tmp_path / "report.xml")
        results = [self._result("t1"), self._result("t2")]
        create_junit_report("suite", results, out, {"urls", "hostnames"}, "prov")
        content = open(out).read()
        assert 'name="hostnames"' in content
        assert 'value="example.com"' in content

    def test_suite_time_equals_sum_of_durations(self, tmp_path):
        from junitparser import JUnitXml as JX
        out = str(tmp_path / "report.xml")
        results = [self._result("t1"), self._result("t2")]  # 2 × 0.5s = 1.0s
        create_junit_report("suite", results, out, set(), "prov")
        xml = JX.fromfile(out)
        for suite in xml:
            assert abs(suite.time - 1.0) < 0.001

    def test_empty_results_still_creates_file(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [], out, set(), "prov")
        assert os.path.exists(out)