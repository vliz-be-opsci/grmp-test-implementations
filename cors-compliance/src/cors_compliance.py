#!/usr/bin/env python3
"""
CORS Compliance Check
Checks CORS headers for one or more URLs and writes a JUnit XML report.

For each URL the following test cases are produced:
  - access_control_allow_origin  [url] [origin]  (one per configured origin)
  - access_control_allow_methods [url]
  - access_control_allow_headers [url]
  - access_control_expose_headers [url]           (Should)
  - https_redirect               [url]            (Should, only if https-redirect: true)
"""

import ast
import contextlib
import io
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import requests
import urllib3
from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped

# SSL verification is intentionally disabled (see _request). Suppress the
# resulting urllib3 warning so it doesn't pollute test output and JUnit stderr.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# Output capture
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def capture_output():
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


# ---------------------------------------------------------------------------
# Config parsing helpers
# ---------------------------------------------------------------------------

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


def _parse_list_env(name, default):
    """
    Parse an env variable expected to be a Python list literal, e.g. "['a', 'b']".
    Falls back to default (a list) on any parse error.
    A bare string (one that is not a valid Python literal, such as a plain '*' or
    an unquoted domain) is treated as a single-element list as a convenience, so
    that YAML scalar values like `access-control-allow-origin: '*'` work without
    requiring the operator to add extra quoting.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        # Not a Python literal — treat the raw string itself as a single value.
        return [raw]
    if isinstance(parsed, str):
        return [parsed]
    if isinstance(parsed, (list, tuple)):
        return [v for v in parsed if isinstance(v, str) and v]
    print(f"Invalid {name}={raw!r}; must be a list of strings. Falling back to default", file=sys.stderr)
    return default


def _parse_origins(raw_origins):
    """
    Validate the parsed list of origins.
    Returns (origins, error) where:
      - origins is None  → lenient mode: accept '*' or probe origin in response
      - origins is a list → strict mode: each origin is checked individually
    A list mixing '*' with specific origins is rejected.
    """
    if raw_origins is None:
        return None, None
    if not raw_origins:
        return None, None
    has_wildcard = "*" in raw_origins
    has_specific = any(o != "*" for o in raw_origins)
    if has_wildcard and has_specific:
        return None, "access-control-allow-origin cannot mix '*' with specific origins"
    return raw_origins, None


def parse_config():
    raw_urls = _parse_list_env("TEST_URLS", [])
    urls = [u for u in raw_urls if isinstance(u, str) and u]

    raw_origins = _parse_list_env("TEST_ACCESS-CONTROL-ALLOW-ORIGIN", None)
    origins, origin_error = _parse_origins(raw_origins)
    if origin_error:
        print(f"Config error: {origin_error}. Falling back to lenient mode", file=sys.stderr)
        origins = None

    return {
        "urls": urls,
        "origins": origins,
        "allow_methods": _parse_list_env(
            "TEST_ACCESS-CONTROL-ALLOW-METHODS", ["GET", "HEAD", "OPTIONS"]
        ),
        "allow_headers": _parse_list_env(
            "TEST_ACCESS-CONTROL-ALLOW-HEADERS", ["Accept"]
        ),
        "expose_headers": _parse_list_env(
            "TEST_ACCESS-CONTROL-EXPOSE-HEADERS", ["Content-Type", "Link"]
        ),
        "https_redirect": os.environ.get("TEST_HTTPS-REDIRECT", "false").lower() == "true",
        "probe_origin": os.environ.get("TEST_PROBE-ORIGIN", "https://vliz.be"),
        "timeout": _parse_int_env("TEST_TIMEOUT", 30, minimum=1),
        "provenance": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
    }


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _make_session():
    session = requests.Session()
    # Do not follow redirects automatically — we handle them explicitly
    session.max_redirects = 0
    return session


def _request(method, url, headers, timeout, allow_redirects=True):
    """
    Perform an HTTP request.
    SSL verification is intentionally disabled — certificate validity is the
    responsibility of check_certificate, not this test.
    Returns (response, error_string). On network/timeout error response is None.
    """
    try:
        response = requests.request(
            method, url,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
            verify=False,
        )
        return response, None
    except requests.exceptions.Timeout:
        return None, f"Request timed out after {timeout}s"
    except requests.exceptions.SSLError as e:
        return None, f"SSL error: {e}"
    except requests.exceptions.ConnectionError as e:
        return None, f"Connection error: {e}"
    except requests.exceptions.RequestException as e:
        return None, f"Request error: {e}"


def _follow_to_final(method, url, request_headers, timeout):
    """
    Follow redirects manually, returning the final response and all intermediate responses.
    Returns (final_response, redirect_chain, hop_responses, error_string).
    redirect_chain is a list of (from_url, to_url, status_code) tuples.
    hop_responses is a list of (url, response) pairs for every redirect response in order,
    not including the final non-redirect response (which is returned as final_response).
    """
    current_url = url
    chain = []
    hop_responses = []
    seen = set()
    max_hops = 10

    for _ in range(max_hops):
        if current_url in seen:
            return None, chain, hop_responses, f"Redirect loop detected at {current_url}"
        seen.add(current_url)

        response, err = _request(method, current_url, request_headers, timeout, allow_redirects=False)
        if err:
            return None, chain, hop_responses, err

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("Location")
            if not location:
                return None, chain, hop_responses, f"Redirect response {response.status_code} missing Location header"
            # Resolve relative redirects
            next_url = urllib.parse.urljoin(current_url, location)
            chain.append((current_url, next_url, response.status_code))
            hop_responses.append((current_url, response))
            current_url = next_url
        else:
            return response, chain, hop_responses, None

    return None, chain, hop_responses, f"Too many redirects (>{max_hops})"


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _result(case_name, url, *, failure_message=None, failure_text=None,
            error=None, skipped=False, skipped_message="",
            stdout="", stderr="", duration=0.0, properties=None):
    return {
        "case_name": case_name,
        "duration": duration,
        "error": error,
        "failure_message": failure_message,
        "failure_text": failure_text,
        "properties": properties if properties is not None else {"urls": url, "hostnames": _hostname(url)},
        "skipped": skipped,
        "skipped_message": skipped_message,
        "stdout": stdout,
        "stderr": stderr,
    }


def skipped_test(case_name, reason):
    return _result(case_name, "", skipped=True, skipped_message=reason, properties={})


def _hostname(url):
    try:
        return urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return ""


_DEFAULT_PORTS = {"http": 80, "https": 443}

def _origin_tuple(url):
    """
    Return a (scheme, hostname, port) tuple for origin comparison.
    Explicit default ports are normalised to None so that
    https://example.com and https://example.com:443 compare as equal.
    """
    try:
        p = urllib.parse.urlparse(url)
        scheme = p.scheme.lower()
        port = p.port
        if port == _DEFAULT_PORTS.get(scheme):
            port = None
        return (scheme, p.hostname or "", port)
    except Exception:
        return ("", "", None)


# ---------------------------------------------------------------------------
# Individual test runners
# ---------------------------------------------------------------------------

def run_allow_origin_test(url, origin, probe_origin, timeout):
    """
    Test access-control-allow-origin for a single URL/origin combination.

    Three modes depending on the value of origin:
      - None (lenient): sends probe_origin, accepts '*' or probe_origin in response
      - '*' (wildcard):  sends probe_origin, asserts response is exactly '*'
      - '<domain>' (specific): sends that domain, asserts it is reflected back exactly

    In the specific domain case, probe_origin is ignored — the domain is both
    the sent Origin and the expected response value, since a server configured
    to allow only that domain will only reflect it back if it receives it.
    """
    case_name = f"access_control_allow_origin [{url}] [{'lenient' if origin is None else origin}]"
    sending_origin = origin if (origin is not None and origin != "*") else probe_origin
    request_headers = {"Origin": sending_origin}

    start = time.time()
    with capture_output() as (out, err):
        print(f"OPTIONS {url} with Origin: {sending_origin}")
        response, chain, _, req_err = _follow_to_final("OPTIONS", url, request_headers, timeout)

        if req_err:
            print(f"Request failed: {req_err}", file=sys.stderr)
            duration = time.time() - start
            return _result(case_name, url, error=f"Request failed: {req_err}",
                           stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)

        if chain:
            print(f"Followed {len(chain)} redirect(s) to {response.url}")

        actual = response.headers.get("access-control-allow-origin", "").strip()
        print(f"access-control-allow-origin: {actual!r}")

        failure_message = None
        failure_text = None

        if not actual:
            failure_message = "Header 'access-control-allow-origin' is missing"
            failure_text = (
                f"Header absent in response from {response.url}"
            )
        elif origin is None:
            # Lenient mode: accept either wildcard or the probe origin being reflected
            if actual != "*" and actual != probe_origin:
                failure_message = "access-control-allow-origin does not recognise the probe origin"
                failure_text = (
                    f"Expected '*' or {probe_origin!r} but got {actual!r}"
                )
        elif origin == "*" and actual != "*":
            failure_message = "access-control-allow-origin does not allow all origins"
            failure_text = f"Expected '*' but got {actual!r}"
        elif origin != "*" and actual != origin:
            failure_message = "access-control-allow-origin does not reflect the requested origin"
            failure_text = f"Expected {origin!r} but got {actual!r}"

    duration = time.time() - start
    return _result(case_name, url, failure_message=failure_message, failure_text=failure_text,
                   stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)


def run_allow_methods_test(url, expected_methods, timeout):
    """
    Test access-control-allow-methods via OPTIONS preflight.
    Asserts configured methods are a subset of the server's advertised methods.
    """
    case_name = f"access_control_allow_methods [{url}]"
    request_headers = {"Origin": "https://vliz.be", "Access-Control-Request-Method": "GET"}

    start = time.time()
    with capture_output() as (out, err):
        print(f"OPTIONS {url} (checking allow-methods)")
        response, chain, _, req_err = _follow_to_final("OPTIONS", url, request_headers, timeout)

        if req_err:
            print(f"Request failed: {req_err}", file=sys.stderr)
            duration = time.time() - start
            return _result(case_name, url, error=f"Request failed: {req_err}",
                           stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)

        raw = response.headers.get("access-control-allow-methods", "")
        print(f"access-control-allow-methods: {raw!r}")
        advertised = {m.strip().upper() for m in raw.split(",") if m.strip()}
        required = {m.strip().upper() for m in expected_methods}

        failure_message = None
        failure_text = None

        if not raw.strip():
            failure_message = "Header 'access-control-allow-methods' is missing"
            failure_text = f"Expected methods {sorted(required)} but header was absent"
        else:
            missing = required - advertised
            if missing:
                failure_message = "access-control-allow-methods is missing required methods"
                failure_text = (
                    f"Missing: {sorted(missing)}\n"
                    f"Advertised: {sorted(advertised)}\n"
                    f"Required: {sorted(required)}"
                )

    duration = time.time() - start
    return _result(case_name, url, failure_message=failure_message, failure_text=failure_text,
                   stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)


def run_allow_headers_test(url, expected_headers, timeout):
    """
    Test access-control-allow-headers via OPTIONS preflight.
    Asserts configured headers are a subset of the server's advertised headers.
    """
    case_name = f"access_control_allow_headers [{url}]"
    request_headers = {
        "Origin": "https://vliz.be",
        "Access-Control-Request-Headers": ", ".join(expected_headers),
    }

    start = time.time()
    with capture_output() as (out, err):
        print(f"OPTIONS {url} (checking allow-headers)")
        response, chain, _, req_err = _follow_to_final("OPTIONS", url, request_headers, timeout)

        if req_err:
            print(f"Request failed: {req_err}", file=sys.stderr)
            duration = time.time() - start
            return _result(case_name, url, error=f"Request failed: {req_err}",
                           stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)

        raw = response.headers.get("access-control-allow-headers", "")
        print(f"access-control-allow-headers: {raw!r}")
        advertised = {h.strip().lower() for h in raw.split(",") if h.strip()}
        required = {h.strip().lower() for h in expected_headers}

        failure_message = None
        failure_text = None

        if not raw.strip():
            failure_message = "Header 'access-control-allow-headers' is missing"
            failure_text = f"Expected headers {sorted(required)} but header was absent"
        else:
            missing = required - advertised
            if missing:
                failure_message = "access-control-allow-headers is missing required headers"
                failure_text = (
                    f"Missing: {sorted(missing)}\n"
                    f"Advertised: {sorted(advertised)}\n"
                    f"Required: {sorted(required)}"
                )

    duration = time.time() - start
    return _result(case_name, url, failure_message=failure_message, failure_text=failure_text,
                   stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)


def run_expose_headers_test(url, expected_headers, probe_origin, timeout):
    """
    Test access-control-expose-headers via GET request.
    Asserts configured headers are a subset of the server's exposed headers.
    """
    case_name = f"access_control_expose_headers [{url}]"
    request_headers = {"Origin": probe_origin}

    start = time.time()
    with capture_output() as (out, err):
        print(f"GET {url} (checking expose-headers)")
        response, chain, _, req_err = _follow_to_final("GET", url, request_headers, timeout)

        if req_err:
            print(f"Request failed: {req_err}", file=sys.stderr)
            duration = time.time() - start
            return _result(case_name, url, error=f"Request failed: {req_err}",
                           stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)

        raw = response.headers.get("access-control-expose-headers", "")
        print(f"access-control-expose-headers: {raw!r}")
        advertised = {h.strip().lower() for h in raw.split(",") if h.strip()}
        required = {h.strip().lower() for h in expected_headers}

        failure_message = None
        failure_text = None

        if not raw.strip():
            failure_message = "Header 'access-control-expose-headers' is missing"
            failure_text = f"Expected headers {sorted(required)} but header was absent"
        else:
            missing = required - advertised
            if missing:
                failure_message = "access-control-expose-headers is missing required headers"
                failure_text = (
                    f"Missing: {sorted(missing)}\n"
                    f"Advertised: {sorted(advertised)}\n"
                    f"Required: {sorted(required)}"
                )

    duration = time.time() - start
    return _result(case_name, url, failure_message=failure_message, failure_text=failure_text,
                   stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)


def _check_cors_header(actual_origin, expected_origin, probe_origin, hop_url):
    """
    Validate access-control-allow-origin for a single response.
    Returns (failure_message, failure_text) or (None, None) on pass.
    """
    if not actual_origin:
        return (
            "CORS header missing in redirect chain",
            f"'access-control-allow-origin' absent from response at {hop_url}",
        )
    if expected_origin is None:
        if actual_origin != "*" and actual_origin != probe_origin:
            return (
                "access-control-allow-origin incorrect in redirect chain",
                f"Expected '*' or {probe_origin!r} but got {actual_origin!r} at {hop_url}",
            )
    elif expected_origin == "*" and actual_origin != "*":
        return (
            "access-control-allow-origin incorrect in redirect chain",
            f"Expected '*' but got {actual_origin!r} at {hop_url}",
        )
    elif expected_origin != "*" and actual_origin != expected_origin:
        return (
            "access-control-allow-origin incorrect in redirect chain",
            f"Expected {expected_origin!r} but got {actual_origin!r} at {hop_url}",
        )
    return None, None


def run_https_redirect_test(url, probe_origin, expected_origin, timeout):
    """
    Test that HTTP redirects to HTTPS and that access-control-allow-origin is
    present and correct on every response in the chain, including redirect responses.

    Per the Fetch/CORS spec, browsers evaluate CORS headers on every hop — a missing
    or incorrect header on any redirect response will cause the browser to abort the
    request, regardless of whether the final response has correct headers.

    expected_origin is the configured origin (None for lenient, '*' for wildcard,
    or a specific domain).
    """
    case_name = f"https_redirect [{url}]"

    # Derive the HTTP version of the URL
    parsed = urllib.parse.urlparse(url)
    http_url = url.replace("https://", "http://", 1) if parsed.scheme == "https" else url

    request_headers = {"Origin": probe_origin}

    start = time.time()
    with capture_output() as (out, err):
        print(f"GET {http_url} (checking https redirect)")
        response, chain, hop_responses, req_err = _follow_to_final("GET", http_url, request_headers, timeout)

        if req_err:
            print(f"Request failed: {req_err}", file=sys.stderr)
            duration = time.time() - start
            return _result(case_name, url, error=f"Request failed: {req_err}",
                           stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)

        failure_message = None
        failure_text = None

        # Check that the redirect chain contains an HTTP -> HTTPS hop
        https_hop = next(
            ((src, dst, code) for src, dst, code in chain
             if urllib.parse.urlparse(src).scheme == "http"
             and urllib.parse.urlparse(dst).scheme == "https"),
            None,
        )

        if not https_hop:
            final_scheme = urllib.parse.urlparse(response.url).scheme
            failure_message = "No HTTP to HTTPS redirect detected"
            failure_text = (
                f"No redirect from http to https found in chain.\n"
                f"Redirect chain: {chain}\n"
                f"Final URL scheme: {final_scheme}"
            )
            print(failure_text)
        else:
            src, dst, code = https_hop
            print(f"HTTP→HTTPS redirect: {src} → {dst} ({code})")

            # Validate CORS header on every hop response, then on the final response.
            # The spec requires the header on each redirect response — browsers abort
            # on the first hop that is missing or has an incorrect value.
            all_responses = hop_responses + [(response.url, response)]

            for hop_url, hop_resp in all_responses:
                actual_origin = hop_resp.headers.get("access-control-allow-origin", "").strip()
                print(f"access-control-allow-origin at {hop_url}: {actual_origin!r}")
                failure_message, failure_text = _check_cors_header(
                    actual_origin, expected_origin, probe_origin, hop_url
                )
                if failure_message:
                    break

    duration = time.time() - start
    return _result(case_name, url, failure_message=failure_message, failure_text=failure_text,
                   stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)


# ---------------------------------------------------------------------------
# Per-URL orchestration
# ---------------------------------------------------------------------------

def run_tests_for_url(url, config):
    probe_origin = config["probe_origin"]

    # Safety check: probe-origin must not be the same origin as the URL being tested.
    # A server that only returns CORS headers when the Origin matches its own origin
    # is severely misconfigured — same-origin requests bypass CORS entirely, so such
    # a server effectively supports no cross-origin access at all. Allowing the probe
    # origin to equal the resource origin would mask this misconfiguration.
    # Origin identity is defined as scheme + hostname + port, matching browser semantics.
    url_origin = _origin_tuple(url)
    probe_origin_tuple = _origin_tuple(probe_origin)
    if url_origin[0] and url_origin[1] and url_origin == probe_origin_tuple:
        return [skipped_test(
            f"cors_compliance [{url}]",
            f"probe-origin ({probe_origin!r}) must not be the same origin as the URL. "
            f"Set probe-origin to an external origin to avoid masking server misconfigurations.",
        )]

    results = []
    timeout = config["timeout"]

    # Determine the origin to use as the expected value for https_redirect check.
    # If there are multiple specific origins, use the first one as representative.
    representative_origin = config["origins"][0] if config["origins"] else None

    # Must: access-control-allow-origin
    # Lenient mode (origins is None) produces a single test case.
    # Strict mode produces one test case per configured origin.
    for origin in (config["origins"] or [None]):
        results.append(run_allow_origin_test(url, origin, probe_origin, timeout))

    # Must: access-control-allow-methods
    results.append(run_allow_methods_test(url, config["allow_methods"], timeout))

    # Must: access-control-allow-headers
    results.append(run_allow_headers_test(url, config["allow_headers"], timeout))

    # Should: access-control-expose-headers
    results.append(run_expose_headers_test(url, config["expose_headers"], probe_origin, timeout))

    # Should: https-redirect
    if config["https_redirect"]:
        results.append(run_https_redirect_test(url, probe_origin, representative_origin, timeout))

    return results


# ---------------------------------------------------------------------------
# JUnit report
# ---------------------------------------------------------------------------

def create_junit_report(suite_name, results, output_file, special_key_append_properties,
                        provenance, suite_properties=None):
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
    if (origins := suite_properties.get("origins")) is not None:
        suite.add_property("access-control-allow-origin", ", ".join(origins))
    if (allow_methods := suite_properties.get("allow_methods")) is not None:
        suite.add_property("access-control-allow-methods", ", ".join(allow_methods))
    if (allow_headers := suite_properties.get("allow_headers")) is not None:
        suite.add_property("access-control-allow-headers", ", ".join(allow_headers))
    if (expose_headers := suite_properties.get("expose_headers")) is not None:
        suite.add_property("access-control-expose-headers", ", ".join(expose_headers))
    if (https_redirect := suite_properties.get("https_redirect")) is not None:
        suite.add_property("https-redirect", str(https_redirect).lower())
    if (probe_origin := suite_properties.get("probe_origin")) is not None:
        suite.add_property("probe-origin", probe_origin)
    suite.add_property("provenance", provenance)
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "cors-compliance")
    config = parse_config()

    if not config["urls"]:
        results = [skipped_test("cors_compliance", "No URL(s) configured")]
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