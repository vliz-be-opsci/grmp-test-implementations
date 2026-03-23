#!/usr/bin/env python3
"""
Certificate Check
Checks TLS certificate expiration for one or more URLs and writes a JUnit XML report.
"""

import contextlib
import io
import os
import socket
import ssl
import sys
import ast
import urllib.parse
import time
from datetime import datetime, timezone

from cryptography import x509
from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped


@contextlib.contextmanager
def capture_output():
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def _parse_list_env(name, default):
    """
    Parse an env variable expected to be a Python list literal, e.g. "['a', 'b']".
    A bare string (not a valid Python literal) is treated as a single-element list,
    so plain values like TEST_URLS=https://example.com work without extra quoting.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return [raw]
    if isinstance(parsed, str):
        return [parsed]
    if isinstance(parsed, (list, tuple)):
        return [v.strip() for v in parsed if isinstance(v, str) and v.strip()]
    print(f"Invalid {name}={raw!r}; must be a list of strings. Falling back to default",
          file=sys.stderr)
    return default


def _parse_int_env(name, default, *, minimum=None):
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}; falling back to {default}", file=sys.stderr)
        return default
    if minimum is not None and value < minimum:
        print(
            f"Invalid {name}={raw!r}; must be >= {minimum}. Falling back to {default}",
            file=sys.stderr,
        )
        return default
    return value


def parse_config():
    urls = _parse_list_env("TEST_URLS", [])

    return {
        "urls": urls,
        "timeout": _parse_int_env("TEST_TIMEOUT", 30, minimum=1),
        "expiry_days": _parse_int_env("TEST_CERTIFICATE-EXPIRY-DAYS", 30, minimum=0),
        "provenance": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
        "create_issue": os.environ.get("SPECIAL_CREATE_ISSUE", "false").lower() == "true",
    }


def get_certificate_expiry(hostname, port=443, timeout=30):
    """
    Fetch the TLS certificate for hostname:port and return its expiry datetime.
    Verification is intentionally disabled so that expired certificates can be
    retrieved and evaluated rather than causing a handshake error.
    The raw DER-encoded certificate is parsed with the cryptography library,
    which also makes this function forward-compatible with CRL/OCSP checks.
    Returns (expiry_dt, error) where expiry_dt is a timezone-aware datetime or None on error.
    """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert_der = ssock.getpeercert(binary_form=True)
    except ssl.SSLError as e:
        return None, f"SSL error: {e}"
    except socket.timeout:
        return None, f"Connection timed out after {timeout}s"
    except socket.gaierror as e:
        return None, f"DNS resolution failed: {e}"
    except OSError as e:
        return None, f"Connection error: {e}"

    if not cert_der:
        return None, "No certificate returned by server"

    try:
        cert = x509.load_der_x509_certificate(cert_der)
    except Exception as e:
        return None, f"Failed to parse certificate: {e}"

    return cert.not_valid_after_utc, None


def check_expiry(expiry_dt, expiry_days, now=None):
    """
    Evaluate certificate expiry against the current time and warning threshold.
    Returns (status, message) where status is 'ok', 'warn', or 'expired'.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if expiry_dt <= now:
        return "expired", f"Certificate expired on {expiry_dt.isoformat()}"

    days_remaining = (expiry_dt - now).days
    if days_remaining < expiry_days:
        return "warn", (
            f"Certificate expires in {days_remaining} day(s) "
            f"(threshold: {expiry_days} days, expiry: {expiry_dt.isoformat()})"
        )

    return "ok", (
        f"Certificate valid for {days_remaining} more day(s) "
        f"(expiry: {expiry_dt.isoformat()})"
    )


def skipped_test(case_name, reason):
    return {
        "case_name": case_name,
        "duration": 0.0,
        "error": None,
        "failure_message": None,
        "failure_text": None,
        "properties": {},
        "skipped": True,
        "skipped_message": reason,
        "stdout": "",
        "stderr": "",
    }


def _malformed_url_result(url, reason):
    return {
        "case_name": f"certificate_expiry [{url}]",
        "duration": 0.0,
        "error": f"Malformed URL: {reason}",
        "failure_message": None,
        "failure_text": None,
        "properties": {"urls": url, "hostnames": ""},
        "skipped": False,
        "skipped_message": "",
        "stdout": "",
        "stderr": "",
    }


def run_expiry_test(url, timeout, expiry_days):
    """Check certificate expiration for a single URL."""
    parsed = urllib.parse.urlparse(url)
    hostname = parsed.hostname

    try:
        port = parsed.port or 443
    except ValueError:
        return _malformed_url_result(url, f"invalid port in '{url}'")

    if not hostname:
        return _malformed_url_result(url, f"could not extract hostname from '{url}'")

    failure_message = None
    failure_text = None
    error = None
    properties = {"urls": url, "hostnames": hostname or ""}

    start = time.time()
    with capture_output() as (out, err):
        print(f"Checking certificate expiry for: {hostname}:{port}")

        expiry_dt, fetch_error = get_certificate_expiry(hostname, port=port, timeout=timeout)

        if fetch_error:
            print(f"Failed to retrieve certificate: {fetch_error}", file=sys.stderr)
            error = f"Could not retrieve certificate: {fetch_error}"
        else:
            status, message = check_expiry(expiry_dt, expiry_days)
            print(f"expiry: {expiry_dt.isoformat()}")
            print(f"status: {status}")
            print(message)

            if status == "expired":
                failure_message = "Certificate has expired"
                failure_text = message
            elif status == "warn":
                failure_message = "Certificate expiring soon"
                failure_text = message

    duration = time.time() - start

    return {
        "case_name": f"certificate_expiry [{url}]",
        "duration": duration,
        "error": error,
        "failure_message": failure_message,
        "failure_text": failure_text,
        "properties": properties,
        "skipped": False,
        "skipped_message": "",
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
    }


def run_tests_for_url(url, config):
    return [run_expiry_test(url, config["timeout"], config["expiry_days"])]


def create_junit_report(suite_name, results, output_file, special_key_append_properties, provenance, suite_properties=None):
    suite = TestSuite(suite_name)
    suite.timestamp = datetime.now(timezone.utc).isoformat()
    if suite_properties is None:
        suite_properties = {}
    total_time = 0.0
    added_properties = set()
    append_properties = {}

    for result in results:
        case = TestCase(result["case_name"], classname=suite_name)
        case.time = result["duration"]
        total_time += result["duration"]

        for key, value in result["properties"].items():
            if key in special_key_append_properties:
                if key not in append_properties:
                    append_properties[key] = []
                append_properties[key].append(value)
            elif key not in added_properties:
                suite.add_property(key, value)
                added_properties.add(key)

        if result["skipped"]:
            case.result = [Skipped(message=result["skipped_message"])]
        else:
            if result["error"] is not None:
                err = Error(message="Unexpected error")
                err.text = str(result["error"])
                case.result = [err]
            elif result["failure_message"]:
                failure = Failure(message=result["failure_message"])
                failure.text = result["failure_text"]
                case.result = [failure]
            if result.get("stdout"):
                case.system_out = result["stdout"]
            if result.get("stderr"):
                case.system_err = result["stderr"]

        suite.add_testcase(case)

    for key, values in append_properties.items():
        seen = dict.fromkeys(str(v) for v in values if v is not None and str(v) != "")
        if seen:
            suite.add_property(key, ", ".join(seen))

    if (timeout := suite_properties.get("timeout")) is not None:
        suite.add_property("timeout", str(timeout))
    if (expiry_days := suite_properties.get("expiry_days")) is not None:
        suite.add_property("certificate-expiry-days", str(expiry_days))
    suite.add_property("provenance", provenance)
    suite.add_property("create-issue", str(suite_properties.get("create_issue", False)).lower())
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "certificate-check")
    config = parse_config()

    if not config["urls"]:
        results = [skipped_test("certificate_check", "No URL(s) configured")]
    else:
        results = []
        for url in config["urls"]:
            results.extend(run_tests_for_url(url, config))

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(
        suite_name, results, output_file=report_path,
        special_key_append_properties={"urls", "hostnames"},
        provenance=config["provenance"],
        suite_properties=config,
    )