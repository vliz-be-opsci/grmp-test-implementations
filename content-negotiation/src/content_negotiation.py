#!/usr/bin/env python3
"""
Content Negotiation Check
Checks content negotiation for one or more URLs and writes a JUnit XML report.

For each URL and each configured Accept header the following test case is produced:
  - content_negotiation [url] [accept-header]

Each test case asserts:
  1. The response status is 2xx.
  2. The response Content-Type matches the Accept header:
       - Simple header (e.g. "text/turtle"): exact match after stripping parameters.
       - Complex header (e.g. with q-values): response type is one of the listed types.
  3. If check-response-body-conformity is enabled and the content-type assertion passed:
     the response body parses without error using rdflib. Non-RDF types and */* are skipped.
"""

import ast
import contextlib
import io
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import rdflib
import requests
import urllib3
from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped

# SSL verification is intentionally disabled. Suppress the urllib3 warning.
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
    A bare string (not a valid Python literal) is treated as a single-element list,
    so YAML scalar values work without requiring extra Python-style quoting.
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
        return [v for v in parsed if isinstance(v, str) and v]
    print(f"Invalid {name}={raw!r}; must be a list of strings. Falling back to default",
          file=sys.stderr)
    return default


def parse_config():
    raw_urls = _parse_list_env("TEST_URLS", [])
    urls = [u for u in raw_urls if isinstance(u, str) and u]

    accept_headers = _parse_list_env("TEST_ACCEPT-HEADERS", None)

    check_body = os.environ.get("TEST_CHECK-RESPONSE-BODY-CONFORMITY", "").lower()
    check_body_conformity = True if check_body == "true" else (
        False if check_body == "false" else None
    )

    return {
        "urls": urls,
        "accept_headers": accept_headers,
        "check_body_conformity": check_body_conformity,
        "timeout": _parse_int_env("TEST_TIMEOUT", 30, minimum=1),
        "provenance": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
        "create_issue": os.environ.get("SPECIAL_CREATE_ISSUE", "false").lower() == "true",
    }


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _request(url, accept_header, timeout):
    """Send a GET request with the given Accept header. Returns (response, error)."""
    try:
        response = requests.get(
            url,
            headers={"Accept": accept_header},
            timeout=timeout,
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


# ---------------------------------------------------------------------------
# Accept header parsing
# ---------------------------------------------------------------------------

def _parse_accept_header(accept_header):
    """
    Parse an Accept header string into a list of media types (parameters stripped).
    E.g. "text/turtle" -> ["text/turtle"]
         "application/ld+json, text/turtle;q=0.9, */*;q=0.1" -> ["application/ld+json", "text/turtle", "*/*"]
    """
    types = []
    for part in accept_header.split(","):
        part = part.strip()
        # Strip parameters (q-values, charset, etc.)
        media_type = part.split(";")[0].strip().lower()
        if media_type:
            types.append(media_type)
    return types


def _is_complex_accept_header(accept_header):
    """Returns True if the Accept header contains multiple types or q-values."""
    return "," in accept_header or ";" in accept_header


def _extract_response_content_type(response):
    """Extract the bare media type from the response Content-Type header."""
    raw = response.headers.get("content-type", "")
    return raw.split(";")[0].strip().lower()


# ---------------------------------------------------------------------------
# RDF content type detection and body conformity check
# ---------------------------------------------------------------------------

# Mapping from media type to rdflib format string.
# Types not in this map are considered non-RDF and skipped for conformity.
_RDFLIB_FORMATS = {
    "text/turtle":                "turtle",
    "application/ld+json":        "json-ld",
    "application/trig":           "trig",
    "application/n-quads":        "nquads",
    "application/n-triples":      "nt",
    "application/rdf+xml":        "xml",
    "text/n3":                    "n3",
}


def _check_body_conformity(body, content_type):
    """
    Attempt to parse the response body with rdflib using the given content type.
    Returns (skipped, failure_message, failure_text).
    - skipped=True if the content type is not a known RDF type.
    - failure_message is set if parsing fails.
    """
    rdflib_format = _RDFLIB_FORMATS.get(content_type)
    if rdflib_format is None:
        return True, None, None

    try:
        g = rdflib.Graph()
        g.parse(source=io.BytesIO(body.encode("utf-8")), format=rdflib_format)
        return False, None, None
    except Exception as e:
        return False, f"Response body does not conform to {content_type}", str(e)


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _hostname(url):
    return urllib.parse.urlparse(url).hostname or url


def _result(case_name, url, *, failure_message=None, failure_text=None,
            error=None, skipped=False, skipped_message="",
            stdout="", stderr="", duration=0.0, properties=None):
    return {
        "case_name": case_name,
        "duration": duration,
        "error": error,
        "failure_message": failure_message,
        "failure_text": failure_text,
        "properties": properties if properties is not None else {
            "urls": url,
            "hostnames": _hostname(url),
        },
        "skipped": skipped,
        "skipped_message": skipped_message,
        "stdout": stdout,
        "stderr": stderr,
    }


def skipped_test(case_name, reason):
    return _result(case_name, "", skipped=True, skipped_message=reason, properties={})


# ---------------------------------------------------------------------------
# Per-accept-header tests
# ---------------------------------------------------------------------------

def run_content_negotiation_test(url, accept_header, timeout):
    """
    Test content negotiation for a single URL and Accept header value.

    Asserts:
      1. Response status is 2xx.
      2. Response Content-Type matches the requested type(s).

    Returns (result, response, matched_content_type) where:
      - response is the HTTP response (or None on request error)
      - matched_content_type is the bare response media type if the test passed,
        or None if it failed — used by run_body_conformity_test to decide whether
        to run or skip.
    """
    case_name = f"content_negotiation [{url}] [{accept_header}]"
    requested_types = _parse_accept_header(accept_header)
    is_complex = _is_complex_accept_header(accept_header)

    start = time.time()
    with capture_output() as (out, err):
        print(f"GET {url}")
        print(f"Accept: {accept_header}")

        response, req_err = _request(url, accept_header, timeout)

        if req_err:
            print(f"Request failed: {req_err}", file=sys.stderr)
            duration = time.time() - start
            return (
                _result(case_name, url, error=f"Request failed: {req_err}",
                        stdout=out.getvalue(), stderr=err.getvalue(), duration=duration),
                None, None,
            )

        failure_message = None
        failure_text = None
        matched_content_type = None

        print(f"Status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('content-type', '(absent)')}")

        # 1. Check status is 2xx
        if not (200 <= response.status_code < 300):
            failure_message = f"Unexpected status code {response.status_code}"
            failure_text = (
                f"Expected a 2xx response but got {response.status_code}.\n"
                f"URL: {url}\n"
                f"Accept: {accept_header}"
            )
        else:
            response_type = _extract_response_content_type(response)
            print(f"Parsed response content-type: {response_type!r}")

            # 2. Check Content-Type matches the Accept header
            if not response_type:
                failure_message = "Response is missing Content-Type header"
                failure_text = (
                    f"No Content-Type header in response.\n"
                    f"URL: {url}\n"
                    f"Accept: {accept_header}"
                )
            elif is_complex:
                # For complex headers: response type must be one of the listed types,
                # but */* is excluded as it provides no useful constraint.
                checkable = [t for t in requested_types if t != "*/*"]
                if checkable and response_type not in checkable:
                    failure_message = "Response Content-Type not in requested types"
                    failure_text = (
                        f"Response Content-Type {response_type!r} is not among "
                        f"the requested types: {checkable}\n"
                        f"URL: {url}\n"
                        f"Accept: {accept_header}"
                    )
                else:
                    matched_content_type = response_type
            else:
                # Simple header: exact match (after parameter stripping)
                expected = requested_types[0] if requested_types else ""
                if expected == "*/*":
                    # */* as sole Accept value — any response type is acceptable
                    matched_content_type = response_type
                elif response_type != expected:
                    failure_message = "Response Content-Type does not match requested type"
                    failure_text = (
                        f"Expected {expected!r} but got {response_type!r}.\n"
                        f"URL: {url}\n"
                        f"Accept: {accept_header}"
                    )
                else:
                    matched_content_type = response_type

    duration = time.time() - start
    result = _result(case_name, url, failure_message=failure_message, failure_text=failure_text,
                     stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)
    return result, response, matched_content_type


def run_body_conformity_test(url, accept_header, response, matched_content_type):
    """
    Test that the response body conforms to its content type using rdflib.

    Should only be called after run_content_negotiation_test. If matched_content_type
    is None (i.e. the content negotiation test failed or errored), the test is skipped.
    Non-RDF content types are also skipped.
    """
    case_name = f"body_conformity [{url}] [{accept_header}]"

    if matched_content_type is None:
        return skipped_test(
            case_name,
            "Skipped because the content negotiation test did not pass.",
        )

    start = time.time()
    with capture_output() as (out, err):
        print(f"Checking body conformity for content-type {matched_content_type!r}")
        skipped_conformity, failure_message, failure_text = \
            _check_body_conformity(response.text, matched_content_type)
        if skipped_conformity:
            duration = time.time() - start
            return _result(
                case_name, url,
                skipped=True,
                skipped_message=f"Body conformity check not supported for non-RDF type {matched_content_type!r}",
                stdout=out.getvalue(), stderr=err.getvalue(), duration=duration,
            )
        if not failure_message:
            print("Body conforms.")

    duration = time.time() - start
    return _result(case_name, url, failure_message=failure_message, failure_text=failure_text,
                   stdout=out.getvalue(), stderr=err.getvalue(), duration=duration)


# ---------------------------------------------------------------------------
# Per-URL orchestration
# ---------------------------------------------------------------------------

def run_tests_for_url(url, config):
    results = []
    for accept_header in config["accept_headers"]:
        cn_result, response, matched_content_type = run_content_negotiation_test(
            url, accept_header, config["timeout"]
        )
        results.append(cn_result)
        if config["check_body_conformity"]:
            results.append(run_body_conformity_test(
                url, accept_header, response, matched_content_type
            ))
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
                error = Error(message="Unexpected error")
                error.text = str(result["error"])
                case.result = [error]
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
    if (accept_headers := suite_properties.get("accept_headers")) is not None:
        for header in accept_headers:
            suite.add_property("accept-header", header)
    if (check_body := suite_properties.get("check_body_conformity")) is not None:
        suite.add_property("check-response-body-conformity", str(check_body).lower())
    suite.add_property("provenance", provenance)
    suite.add_property("create-issue", str(suite_properties.get("create_issue", False)).lower())
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "content-negotiation")
    config = parse_config()

    if not config["urls"]:
        results = [skipped_test("content_negotiation", "No URL(s) configured")]
    elif not config["accept_headers"]:
        results = [skipped_test("content_negotiation", "No Accept header(s) configured")]
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