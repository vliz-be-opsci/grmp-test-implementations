#!/usr/bin/env python3
"""
Unit tests for check_certificate.py

Run with (from certificate-check/ root):
    pip install pytest junitparser cryptography
    pytest tests/test_check_certificate.py -v
"""

import sys
import os
import ssl
import socket
from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from check_certificate import (
    get_certificate_expiry,
    check_expiry,
    run_expiry_test,
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

def make_cert_der(days_from_now):
    """
    Return a mock DER blob (bytes) and a corresponding mock x509 certificate
    object whose not_valid_after_utc is set to now + days_from_now.
    The actual bytes are meaningless — x509.load_der_x509_certificate is always
    patched in tests that use this helper.
    """
    expiry_dt = datetime.now(timezone.utc) + timedelta(days=days_from_now)
    mock_cert = MagicMock()
    mock_cert.not_valid_after_utc = expiry_dt
    return b"fake-der-bytes", mock_cert


def utcnow():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# get_certificate_expiry
# ---------------------------------------------------------------------------

class TestGetCertificateExpiry:
    def _mock_ssl_context(self, cert_der, mock_cert):
        """
        Build mock SSL context and socket so that:
        - ssock.getpeercert(binary_form=True) returns cert_der
        - x509.load_der_x509_certificate(cert_der) returns mock_cert
        """
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = cert_der
        mock_ssock.__enter__ = lambda s: s
        mock_ssock.__exit__ = MagicMock(return_value=False)

        mock_sock = MagicMock()
        mock_sock.__enter__ = lambda s: s
        mock_sock.__exit__ = MagicMock(return_value=False)

        mock_context = MagicMock()
        mock_context.wrap_socket.return_value = mock_ssock

        return mock_context, mock_sock

    def test_returns_expiry_datetime_on_success(self):
        cert_der, mock_cert = make_cert_der(90)
        mock_context, mock_sock = self._mock_ssl_context(cert_der, mock_cert)
        with patch("ssl.create_default_context", return_value=mock_context), \
             patch("socket.create_connection", return_value=mock_sock), \
             patch("check_certificate.x509.load_der_x509_certificate", return_value=mock_cert):
            expiry_dt, error = get_certificate_expiry("example.com")
        assert error is None
        assert isinstance(expiry_dt, datetime)
        assert expiry_dt.tzinfo == timezone.utc

    def test_expiry_date_is_approximately_correct(self):
        cert_der, mock_cert = make_cert_der(90)
        mock_context, mock_sock = self._mock_ssl_context(cert_der, mock_cert)
        with patch("ssl.create_default_context", return_value=mock_context), \
             patch("socket.create_connection", return_value=mock_sock), \
             patch("check_certificate.x509.load_der_x509_certificate", return_value=mock_cert):
            expiry_dt, _ = get_certificate_expiry("example.com")
        expected = utcnow() + timedelta(days=90)
        assert abs((expiry_dt - expected).total_seconds()) < 60

    def test_cert_none_is_set_so_expired_certs_do_not_raise(self):
        """Verification must be disabled so expired certs can be inspected rather than erroring."""
        captured_context = {}
        cert_der, mock_cert = make_cert_der(-1)

        def fake_create_default_context():
            ctx = MagicMock()
            captured_context["ctx"] = ctx
            ctx.check_hostname = True        # will be overwritten
            ctx.verify_mode = ssl.CERT_REQUIRED  # will be overwritten
            mock_ssock = MagicMock()
            mock_ssock.getpeercert.return_value = cert_der
            mock_ssock.__enter__ = lambda s: s
            mock_ssock.__exit__ = MagicMock(return_value=False)
            ctx.wrap_socket.return_value = mock_ssock
            return ctx

        mock_sock = MagicMock()
        mock_sock.__enter__ = lambda s: s
        mock_sock.__exit__ = MagicMock(return_value=False)
        with patch("ssl.create_default_context", side_effect=fake_create_default_context), \
             patch("socket.create_connection", return_value=mock_sock), \
             patch("check_certificate.x509.load_der_x509_certificate", return_value=mock_cert):
            get_certificate_expiry("expired.example.com")
        ctx = captured_context["ctx"]
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_ssl_error_returns_error(self):
        with patch("ssl.create_default_context") as mock_ctx, \
             patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: s
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_ctx.return_value.wrap_socket.side_effect = ssl.SSLError("handshake failure")
            expiry_dt, error = get_certificate_expiry("example.com")
        assert expiry_dt is None
        assert "SSL error" in error

    def test_timeout_returns_error(self):
        with patch("socket.create_connection", side_effect=socket.timeout):
            expiry_dt, error = get_certificate_expiry("example.com", timeout=1)
        assert expiry_dt is None
        assert "timed out" in error

    def test_dns_failure_returns_error(self):
        with patch("socket.create_connection", side_effect=socket.gaierror("Name not known")):
            expiry_dt, error = get_certificate_expiry("nonexistent.invalid")
        assert expiry_dt is None
        assert "DNS resolution failed" in error

    def test_connection_error_returns_error(self):
        with patch("socket.create_connection", side_effect=OSError("Connection refused")):
            expiry_dt, error = get_certificate_expiry("example.com")
        assert expiry_dt is None
        assert "Connection error" in error

    def test_no_cert_returned_by_server(self):
        """getpeercert(binary_form=True) returning None/empty should surface as an error."""
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = None
        mock_ssock.__enter__ = lambda s: s
        mock_ssock.__exit__ = MagicMock(return_value=False)
        mock_sock = MagicMock()
        mock_sock.__enter__ = lambda s: s
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value = mock_ssock
        with patch("ssl.create_default_context", return_value=mock_context), \
             patch("socket.create_connection", return_value=mock_sock):
            expiry_dt, error = get_certificate_expiry("example.com")
        assert expiry_dt is None
        assert "No certificate returned" in error

    def test_unparseable_cert_returns_error(self):
        """A DER blob that cryptography cannot parse should surface as an error."""
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = b"garbage"
        mock_ssock.__enter__ = lambda s: s
        mock_ssock.__exit__ = MagicMock(return_value=False)
        mock_sock = MagicMock()
        mock_sock.__enter__ = lambda s: s
        mock_sock.__exit__ = MagicMock(return_value=False)
        mock_context = MagicMock()
        mock_context.wrap_socket.return_value = mock_ssock
        with patch("ssl.create_default_context", return_value=mock_context), \
             patch("socket.create_connection", return_value=mock_sock), \
             patch("check_certificate.x509.load_der_x509_certificate",
                   side_effect=Exception("invalid DER")):
            expiry_dt, error = get_certificate_expiry("example.com")
        assert expiry_dt is None
        assert "Failed to parse certificate" in error

    def test_custom_port_is_used(self):
        cert_der, mock_cert = make_cert_der(90)
        mock_context = MagicMock()
        mock_ssock = MagicMock()
        mock_ssock.getpeercert.return_value = cert_der
        mock_ssock.__enter__ = lambda s: s
        mock_ssock.__exit__ = MagicMock(return_value=False)
        mock_context.wrap_socket.return_value = mock_ssock
        captured = {}
        def fake_create_connection(address, timeout):
            captured["address"] = address
            mock_sock = MagicMock()
            mock_sock.__enter__ = lambda s: s
            mock_sock.__exit__ = MagicMock(return_value=False)
            return mock_sock
        with patch("ssl.create_default_context", return_value=mock_context), \
             patch("socket.create_connection", side_effect=fake_create_connection), \
             patch("check_certificate.x509.load_der_x509_certificate", return_value=mock_cert):
            get_certificate_expiry("example.com", port=8443)
        assert captured["address"] == ("example.com", 8443)


# ---------------------------------------------------------------------------
# check_expiry
# ---------------------------------------------------------------------------

class TestCheckExpiry:
    NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_valid_cert_returns_ok(self):
        expiry_dt = self.NOW + timedelta(days=60)
        status, message = check_expiry(expiry_dt, expiry_days=30, now=self.NOW)
        assert status == "ok"
        assert "60" in message

    def test_expired_cert_returns_expired(self):
        expiry_dt = self.NOW - timedelta(days=1)
        status, message = check_expiry(expiry_dt, expiry_days=30, now=self.NOW)
        assert status == "expired"
        assert "expired" in message.lower()

    def test_expiring_within_threshold_returns_warn(self):
        expiry_dt = self.NOW + timedelta(days=10)
        status, message = check_expiry(expiry_dt, expiry_days=30, now=self.NOW)
        assert status == "warn"
        assert "10" in message

    def test_exactly_on_threshold_boundary_returns_warn(self):
        # days_remaining = expiry_days - 1 (timedelta.days truncates hours)
        expiry_dt = self.NOW + timedelta(days=29, hours=23)
        status, _ = check_expiry(expiry_dt, expiry_days=30, now=self.NOW)
        assert status == "warn"

    def test_one_day_past_threshold_returns_ok(self):
        expiry_dt = self.NOW + timedelta(days=31)
        status, _ = check_expiry(expiry_dt, expiry_days=30, now=self.NOW)
        assert status == "ok"

    def test_expiry_message_contains_threshold(self):
        expiry_dt = self.NOW + timedelta(days=5)
        _, message = check_expiry(expiry_dt, expiry_days=14, now=self.NOW)
        assert "14" in message

    def test_expired_message_contains_expiry_date(self):
        expiry_dt = self.NOW - timedelta(days=365)
        _, message = check_expiry(expiry_dt, expiry_days=30, now=self.NOW)
        assert "2023" in message

    def test_zero_expiry_days_threshold_never_warns(self):
        expiry_dt = self.NOW + timedelta(days=1)
        status, _ = check_expiry(expiry_dt, expiry_days=0, now=self.NOW)
        assert status == "ok"


# ---------------------------------------------------------------------------
# skipped_test
# ---------------------------------------------------------------------------

class TestSkippedTest:
    def test_returns_correct_structure(self):
        result = skipped_test("certificate_expiry [https://x.com]", "No URL configured")
        assert result["skipped"] is True
        assert result["skipped_message"] == "No URL configured"
        assert result["case_name"] == "certificate_expiry [https://x.com]"
        assert result["failure_message"] is None
        assert result["error"] is None
        assert result["duration"] == 0.0


# ---------------------------------------------------------------------------
# run_expiry_test
# ---------------------------------------------------------------------------

class TestRunExpiryTest:
    def test_valid_cert_has_no_failure(self):
        expiry_dt = utcnow() + timedelta(days=60)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_valid_cert_stdout_contains_ok_status(self):
        expiry_dt = utcnow() + timedelta(days=60)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert "ok" in result["stdout"].lower()

    def test_expired_cert_sets_failure_not_error(self):
        expiry_dt = utcnow() - timedelta(days=1)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert result["failure_message"] is not None
        assert result["error"] is None
        assert "expired" in result["failure_message"].lower()

    def test_expired_cert_sets_failure(self):
        expiry_dt = utcnow() - timedelta(days=1)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert result["failure_message"] is not None
        assert "expired" in result["failure_message"].lower()

    def test_expiring_soon_sets_failure(self):
        expiry_dt = utcnow() + timedelta(days=5)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert result["failure_message"] is not None
        assert "expiring soon" in result["failure_message"].lower()

    def test_fetch_error_sets_error_not_failure(self):
        with patch("check_certificate.get_certificate_expiry", return_value=(None, "Connection refused")):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert result["error"] is not None
        assert result["failure_message"] is None

    def test_fetch_error_goes_to_stderr(self):
        with patch("check_certificate.get_certificate_expiry", return_value=(None, "Connection refused")):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert "Connection refused" in result["stderr"]

    def test_properties_contain_hostname(self):
        expiry_dt = utcnow() + timedelta(days=60)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert result["properties"]["hostnames"] == "example.com"

    def test_properties_contain_url(self):
        expiry_dt = utcnow() + timedelta(days=60)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert result["properties"]["urls"] == "https://example.com"

    def test_case_name_contains_url(self):
        expiry_dt = utcnow() + timedelta(days=60)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            result = run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert "https://example.com" in result["case_name"]

    def test_custom_port_extracted_from_url(self):
        captured = {}
        def fake_get_cert(hostname, port, timeout):
            captured["port"] = port
            return utcnow() + timedelta(days=60), None
        with patch("check_certificate.get_certificate_expiry", side_effect=fake_get_cert):
            run_expiry_test("https://example.com:8443", timeout=10, expiry_days=30)
        assert captured["port"] == 8443

    def test_default_port_443_used_when_not_specified(self):
        captured = {}
        def fake_get_cert(hostname, port, timeout):
            captured["port"] = port
            return utcnow() + timedelta(days=60), None
        with patch("check_certificate.get_certificate_expiry", side_effect=fake_get_cert):
            run_expiry_test("https://example.com", timeout=10, expiry_days=30)
        assert captured["port"] == 443

    def test_missing_hostname_returns_error(self):
        result = run_expiry_test("https://", timeout=10, expiry_days=30)
        assert result["error"] is not None
        assert "hostname" in result["error"].lower()
        assert result["failure_message"] is None

    def test_invalid_port_returns_error(self):
        result = run_expiry_test("https://example.com:abc", timeout=10, expiry_days=30)
        assert result["error"] is not None
        assert "port" in result["error"].lower()
        assert result["failure_message"] is None


# ---------------------------------------------------------------------------
# run_tests_for_url
# ---------------------------------------------------------------------------

class TestRunTestsForUrl:
    def _config(self, **overrides):
        cfg = {"timeout": 10, "expiry_days": 30}
        cfg.update(overrides)
        return cfg

    def test_returns_one_result_per_url(self):
        expiry_dt = utcnow() + timedelta(days=60)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            results = run_tests_for_url("https://example.com", self._config())
        assert len(results) == 1

    def test_result_case_name_matches_url(self):
        expiry_dt = utcnow() + timedelta(days=60)
        with patch("check_certificate.get_certificate_expiry", return_value=(expiry_dt, None)):
            results = run_tests_for_url("https://example.com", self._config())
        assert "https://example.com" in results[0]["case_name"]


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
    ENV_KEYS = ["TEST_URLS", "TEST_TIMEOUT", "TEST_CERTIFICATE-EXPIRY-DAYS", "SPECIAL_SOURCE_FILE"]

    def _clean(self, monkeypatch):
        for k in self.ENV_KEYS:
            monkeypatch.delenv(k, raising=False)

    def test_defaults(self, monkeypatch):
        self._clean(monkeypatch)
        config = parse_config()
        assert config["urls"] == []
        assert config["timeout"] == 30
        assert config["expiry_days"] == 30
        assert config["provenance"] == "unknown"

    def test_custom_urls(self, monkeypatch):
        monkeypatch.setenv("TEST_URLS", "['https://example.com']")
        assert parse_config()["urls"] == ["https://example.com"]

    def test_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "60")
        assert parse_config()["timeout"] == 60

    def test_custom_expiry_days(self, monkeypatch):
        monkeypatch.setenv("TEST_CERTIFICATE-EXPIRY-DAYS", "14")
        assert parse_config()["expiry_days"] == 14

    def test_provenance_from_env(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "my-config.yaml")
        assert parse_config()["provenance"] == "my-config.yaml"

    def test_invalid_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "not-a-number")
        assert parse_config()["timeout"] == 30

    def test_invalid_expiry_days_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_CERTIFICATE-EXPIRY-DAYS", "not-a-number")
        assert parse_config()["expiry_days"] == 30

    def test_zero_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "0")
        assert parse_config()["timeout"] == 30

    def test_negative_timeout_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "-1")
        assert parse_config()["timeout"] == 30

    def test_negative_expiry_days_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_CERTIFICATE-EXPIRY-DAYS", "-1")
        assert parse_config()["expiry_days"] == 30

    def test_zero_expiry_days_is_valid(self, monkeypatch):
        monkeypatch.setenv("TEST_CERTIFICATE-EXPIRY-DAYS", "0")
        assert parse_config()["expiry_days"] == 0


# ---------------------------------------------------------------------------
# create_junit_report
# ---------------------------------------------------------------------------

class TestCreateJunitReport:
    def _result(self, name="certificate_expiry [https://example.com]",
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
            "stderr": "some err" if error else "",
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

    def test_timeout_property_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov",
                            suite_properties={"timeout": 60, "expiry_days": 14})
        content = open(out).read()
        assert 'name="timeout"' in content
        assert '"60"' in content

    def test_certificate_expiry_days_property_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov",
                            suite_properties={"timeout": 60, "expiry_days": 14})
        content = open(out).read()
        assert 'name="certificate-expiry-days"' in content
        assert '"14"' in content

    def test_suite_properties_absent_does_not_crash(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, set(), "prov")
        content = open(out).read()
        assert os.path.exists(out)
        assert 'name="timeout"' not in content
        assert 'name="certificate-expiry-days"' not in content