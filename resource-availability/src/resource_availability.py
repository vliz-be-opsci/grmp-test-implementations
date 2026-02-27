#!/usr/bin/env python3
"""
Resource Availability Test
Checks DNS resolution, HTTP/HTTPS availability, redirect handling, and response time for one or more URLs.
"""

import contextlib
import io
import os
import socket
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests
from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped


@contextlib.contextmanager
def capture_output():
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def parse_config():
    raw_urls = os.environ.get("TEST_URLS")
    urls = [u.strip() for u in raw_urls.strip("[]").split(",") if u.strip()]

    return {
        "urls": urls,
        "max_redirects": int(os.environ.get("TEST_MAX-REDIRECTS", "0")),
        "timeout": int(os.environ.get("TEST_TIMEOUT", "30")),
        "check_http": os.environ.get("TEST_CHECK-HTTP-AVAILABILITY", "false").lower() == "true",
        "check_https": os.environ.get("TEST_CHECK-HTTPS-AVAILABILITY", "true").lower() == "true",
        "verify_ssl": os.environ.get("TEST_VERIFY-SSL", "true").lower() == "true",
    }


def check_dns(hostname):
    """Resolve hostname to IP. Returns (ip, error)."""
    if hostname is None:
        return None, "Could not extract hostname from URL"
    try:
        ip = socket.gethostbyname(hostname)
    except socket.gaierror as e:
        return None, str(e)
    else:
        return ip, None

def check_url(url, timeout, max_redirects, verify_ssl=True):
    """
    Perform HTTP request, manually following redirects up to max_redirects.
    Does not follow redirects that cross the http/https scheme boundary.
    Returns (status_code, final_url, elapsed_seconds, error_message, crossed_scheme_boundary).
    """
    session = requests.Session()
    current_url = url
    initial_scheme = urllib.parse.urlparse(url).scheme
    redirects_followed = 0
    start = time.time()

    try:
        while True:
            hop_verify = verify_ssl if current_url.startswith("https://") else True
            response = session.get(current_url, timeout=timeout, allow_redirects=False, verify=hop_verify)
            elapsed = time.time() - start

            if 200 <= response.status_code < 300:
                return response.status_code, current_url, elapsed, None, False

            if 300 <= response.status_code < 400:
                location = response.headers.get("Location")
                if not location:
                    return (
                        response.status_code,
                        current_url,
                        elapsed,
                        f"Redirect response {response.status_code} had no Location header",
                        False,
                    )

                next_url = urllib.parse.urljoin(current_url, location)
                next_scheme = urllib.parse.urlparse(next_url).scheme

                # Stop at scheme boundary and report it as informational, not a failure
                if next_scheme != initial_scheme:
                    return (
                        response.status_code,
                        next_url,
                        elapsed,
                        None,
                        True,
                    )

                if redirects_followed >= max_redirects:
                    return (
                        response.status_code,
                        current_url,
                        elapsed,
                        f"Redirect limit reached ({max_redirects}); "
                        f"last status {response.status_code} at {current_url}",
                        False,
                    )

                current_url = next_url
                redirects_followed += 1
                continue

            elapsed = time.time() - start
            return (
                response.status_code,
                current_url,
                elapsed,
                f"Unexpected status code {response.status_code}",
                False,
            )

    except requests.exceptions.Timeout:
        elapsed = time.time() - start
        return None, current_url, elapsed, f"Request timed out after {timeout}s", False
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - start
        return None, current_url, elapsed, str(e), False


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


def run_dns_test(url):
    hostname = urllib.parse.urlparse(url).hostname
    start = time.time()
    failure_message = None
    failure_text = None
    error = None
    properties = {"url": url, "hostname": hostname}

    with capture_output() as (out, err):
        print(f"Resolving hostname: {hostname}")
        ip, dns_error = check_dns(hostname)

        if ip:
            print(f"resolved_ip: {ip}")
        else:
            print(f"DNS resolution failed: {dns_error}", file=sys.stderr)
            failure_message = f"DNS resolution failed for {hostname}"
            failure_text = dns_error

    duration = time.time() - start

    return {
        "case_name": f"dns_resolution[{url}]",
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


def run_availability_test(url, scheme, timeout, max_redirects, verify_ssl=True):
    """Check availability for a specific scheme (http or https)."""
    parsed = urllib.parse.urlparse(url)
    target_url = parsed._replace(scheme=scheme).geturl()
    failure_message = None
    failure_text = None
    error = None
    effective_verify_ssl = verify_ssl if scheme == "https" else True
    properties = {
        "verify_ssl": str(effective_verify_ssl),
    }

    with capture_output() as (out, err):
        status, final_url, elapsed, err_msg, crossed_scheme_boundary = check_url(
            target_url, timeout, max_redirects, verify_ssl
        )

        # Always emit compact result summary to system-out
        print(f"response_time_s: {elapsed:.3f}")
        if status is not None:
            print(f"status_code: {status}")

        if crossed_scheme_boundary:
            next_scheme = urllib.parse.urlparse(final_url).scheme
            print(f"redirects_to: {final_url}")
            print(f"OK: {scheme.upper()} endpoint reachable (redirects to {next_scheme.upper()})")
        else:
            if final_url != target_url:
                print(f"final_url: {final_url}")

            if elapsed >= timeout:
                msg = f"Response time {elapsed:.3f}s exceeded timeout of {timeout}s"
                print(f"Checking {scheme.upper()} availability for: {target_url}", file=sys.stderr)
                print(f"Timeout: {timeout}s, Max redirects: {max_redirects}, Verify SSL: {effective_verify_ssl}", file=sys.stderr)
                print(msg, file=sys.stderr)
                error = msg
            elif err_msg:
                print(f"Checking {scheme.upper()} availability for: {target_url}", file=sys.stderr)
                print(f"Timeout: {timeout}s, Max redirects: {max_redirects}, Verify SSL: {effective_verify_ssl}", file=sys.stderr)
                print(f"Availability check failed: {err_msg}", file=sys.stderr)
                failure_message = f"{scheme.upper()} availability check failed"
                failure_text = err_msg
            else:
                print(f"OK: {scheme.upper()} available, status {status} in {elapsed:.3f}s")

    return {
        "case_name": f"{scheme}_availability[{url}]",
        "duration": elapsed,
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
    results = []

    # DNS
    dns_result = run_dns_test(url)
    results.append(dns_result)
    dns_failed = dns_result["failure_message"] or dns_result["error"]

    # HTTP
    if config["check_http"]:
        if dns_failed:
            results.append(skipped_test(f"http_availability[{url}]", "Skipped due to DNS failure"))
        else:
            results.append(run_availability_test(url, "http", config["timeout"], config["max_redirects"], config["verify_ssl"]))

    # HTTPS
    if config["check_https"]:
        if dns_failed:
            results.append(skipped_test(f"https_availability[{url}]", "Skipped due to DNS failure"))
        else:
            results.append(run_availability_test(url, "https", config["timeout"], config["max_redirects"], config["verify_ssl"]))

    return results


def create_junit_report(suite_name, results, output_file):
    suite = TestSuite(suite_name)
    suite.timestamp = datetime.now(timezone.utc).isoformat()
    total_time = 0.0
    added_properties = set()

    for result in results:
        case = TestCase(result["case_name"], classname=suite_name)
        case.time = result["duration"]
        total_time += result["duration"]

        for key, value in result["properties"].items():
            if key not in added_properties:
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

    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "resource-availability")
    config = parse_config()

    if not config["urls"]:
        results = [skipped_test("resource_availability", "No URL(s) configured")]
    else:
        results = []
        for url in config["urls"]:
            results.extend(run_tests_for_url(url, config))

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(suite_name, results, output_file=report_path)