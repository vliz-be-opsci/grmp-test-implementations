#!/usr/bin/env python3
"""
LDES Validation Test
Fetches RDF graphs from one or more URLs and validates them as Linked Data
Event Streams (LDES), checking for ldes:EventStream declarations and
tree:view relations, then writes a JUnit XML report.
"""

import ast
import contextlib
import io
import os
import sys
import time
from datetime import datetime, timezone

import requests
from junitparser import Error, Failure, JUnitXml, Skipped, TestCase, TestSuite
from rdflib import Graph, Namespace, RDF

LDES = Namespace("https://w3id.org/ldes#")
TREE = Namespace("https://w3id.org/tree#")

RDF_ACCEPT = (
    "text/turtle, application/ld+json, application/rdf+xml, "
    "application/n-triples, text/n3, */*;q=0.1"
)

CONTENT_TYPE_FORMATS = {
    "text/turtle": "turtle",
    "application/x-turtle": "turtle",
    "application/ld+json": "json-ld",
    "application/json": "json-ld",
    "application/rdf+xml": "xml",
    "application/xml": "xml",
    "text/xml": "xml",
    "application/n-triples": "nt",
    "text/n3": "n3",
}


@contextlib.contextmanager
def capture_output():
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


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
    raw_urls = os.environ.get("TEST_URLS", "[]")
    try:
        parsed_urls = ast.literal_eval(raw_urls)
    except (ValueError, SyntaxError):
        parsed_urls = []

    if isinstance(parsed_urls, str):
        parsed_urls = [parsed_urls]
    elif not isinstance(parsed_urls, (list, tuple)):
        raise ValueError("TEST_URLS must be a URL string or list/tuple of URL strings")

    urls = [u for u in parsed_urls if isinstance(u, str) and u]

    return {
        "urls": urls,
        "timeout": _parse_int_env("TEST_TIMEOUT", 30, minimum=1),
        "provenance": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
        "create_issue": os.environ.get("SPECIAL_CREATE_ISSUE", "false").lower()
        == "true",
    }


def _detect_rdf_format(content_type, url):
    """Detect RDF serialisation format from Content-Type header or URL extension."""
    if content_type:
        for ct, fmt in CONTENT_TYPE_FORMATS.items():
            if ct in content_type:
                return fmt
    url_path = url.lower().split("?")[0]
    if url_path.endswith(".ttl"):
        return "turtle"
    if url_path.endswith(".jsonld") or url_path.endswith(".json"):
        return "json-ld"
    if url_path.endswith(".rdf") or url_path.endswith(".owl"):
        return "xml"
    if url_path.endswith(".nt"):
        return "nt"
    if url_path.endswith(".n3"):
        return "n3"
    return "turtle"


def fetch_rdf_graph(url, timeout=30):
    """Fetch a URL and parse it as an rdflib Graph. Returns (graph, error_string)."""
    try:
        response = requests.get(
            url, headers={"Accept": RDF_ACCEPT}, timeout=timeout
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        rdf_format = _detect_rdf_format(content_type, url)
        print(
            f"HTTP {response.status_code}, Content-Type: {content_type!r}, "
            f"format: {rdf_format}"
        )
        g = Graph()
        g.parse(data=response.text, format=rdf_format)
        return g, None
    except Exception as e:
        return None, str(e)


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


def run_ldes_validation(url, timeout=30):
    """
    Validate a URL as an LDES event stream.

    Returns a list of three result dicts:
    1. ldes_harvest         - can the URL be fetched and parsed as RDF?
    2. ldes_event_stream    - does the graph declare an ldes:EventStream?
    3. ldes_tree_view       - does the event stream expose a tree:view?
    """
    results = []

    # ------------------------------------------------------------------
    # Test 1: RDF harvest
    # ------------------------------------------------------------------
    start = time.time()
    graph = None
    with capture_output() as (out, err):
        print(f"Fetching RDF graph from: {url}")
        graph, harvest_error = fetch_rdf_graph(url, timeout=timeout)
        if harvest_error:
            print(f"Failed to fetch/parse RDF: {harvest_error}", file=sys.stderr)
        else:
            print(f"Successfully parsed {len(graph)} triple(s)")

    harvest_duration = time.time() - start
    results.append(
        {
            "case_name": f"ldes_harvest [{url}]",
            "duration": harvest_duration,
            "error": None,
            "failure_message": (
                f"Could not fetch or parse RDF from {url}" if harvest_error else None
            ),
            "failure_text": harvest_error if harvest_error else None,
            "properties": {"urls": url},
            "skipped": False,
            "skipped_message": "",
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
        }
    )

    if harvest_error:
        results.append(
            skipped_test(f"ldes_event_stream [{url}]", "RDF harvest failed")
        )
        results.append(skipped_test(f"ldes_tree_view [{url}]", "RDF harvest failed"))
        return results

    # ------------------------------------------------------------------
    # Test 2: ldes:EventStream declaration
    # ------------------------------------------------------------------
    start = time.time()
    with capture_output() as (out, err):
        event_streams = list(graph.subjects(RDF.type, LDES.EventStream))
        print(f"Found {len(event_streams)} ldes:EventStream declaration(s)")
        for es in event_streams:
            print(f"  EventStream: {es}")
        if not event_streams:
            print(
                "No ldes:EventStream (https://w3id.org/ldes#EventStream) found in graph",
                file=sys.stderr,
            )

    event_stream_duration = time.time() - start
    results.append(
        {
            "case_name": f"ldes_event_stream [{url}]",
            "duration": event_stream_duration,
            "error": None,
            "failure_message": (
                "No ldes:EventStream declaration found" if not event_streams else None
            ),
            "failure_text": (
                f"The graph at {url} does not contain any subject with "
                "rdf:type ldes:EventStream (https://w3id.org/ldes#EventStream)"
                if not event_streams
                else None
            ),
            "properties": {"urls": url},
            "skipped": False,
            "skipped_message": "",
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
        }
    )

    if not event_streams:
        results.append(
            skipped_test(f"ldes_tree_view [{url}]", "No ldes:EventStream found")
        )
        return results

    # ------------------------------------------------------------------
    # Test 3: tree:view relation
    # ------------------------------------------------------------------
    start = time.time()
    with capture_output() as (out, err):
        tree_views = []
        for es in event_streams:
            views = list(graph.objects(es, TREE.view))
            tree_views.extend(views)
        print(f"Found {len(tree_views)} tree:view relation(s)")
        for tv in tree_views:
            print(f"  tree:view: {tv}")
        if not tree_views:
            print(
                "No tree:view (https://w3id.org/tree#view) found for any "
                "ldes:EventStream",
                file=sys.stderr,
            )

    tree_view_duration = time.time() - start
    results.append(
        {
            "case_name": f"ldes_tree_view [{url}]",
            "duration": tree_view_duration,
            "error": None,
            "failure_message": (
                "No tree:view relation found" if not tree_views else None
            ),
            "failure_text": (
                f"None of the ldes:EventStream resources at {url} have a "
                "tree:view (https://w3id.org/tree#view) relation"
                if not tree_views
                else None
            ),
            "properties": {"urls": url},
            "skipped": False,
            "skipped_message": "",
            "stdout": out.getvalue(),
            "stderr": err.getvalue(),
        }
    )

    return results


def create_junit_report(suite_name, results, output_file, provenance, suite_properties=None):
    suite = TestSuite(suite_name)
    suite.timestamp = datetime.now(timezone.utc).isoformat()
    total_time = 0.0
    append_urls = []

    for result in results:
        case = TestCase(result["case_name"], classname=suite_name)
        case.time = result["duration"]
        total_time += result["duration"]

        url = result["properties"].get("urls")
        if url:
            append_urls.append(url)

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

    if append_urls:
        unique_urls = list(dict.fromkeys(append_urls))
        suite.add_property("urls", ", ".join(unique_urls))
    suite.add_property("provenance", provenance)
    if suite_properties is not None:
        suite.add_property(
            "create-issue",
            str(suite_properties.get("create_issue", False)).lower(),
        )
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "ldes-validation")
    config = parse_config()

    if not config["urls"]:
        results = [skipped_test("ldes_validation", "No URL(s) configured")]
    else:
        results = []
        for url in config["urls"]:
            results.extend(run_ldes_validation(url, timeout=config["timeout"]))

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(
        suite_name,
        results,
        output_file=report_path,
        provenance=config["provenance"],
        suite_properties=config,
    )
