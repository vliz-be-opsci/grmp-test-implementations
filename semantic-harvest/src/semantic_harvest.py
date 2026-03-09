#!/usr/bin/env python3
"""
Semantic Harvest Test
Attempts to harvest semantic metadata (RDF graphs) from one or more URLs
using the sema.harvest module from the py-sema library.
"""

import ast
import contextlib
import io
import os
import sys
import time
from datetime import datetime, timezone

from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped
from sema.harvest.url_to_graph import get_graph_for_format


# RDF content types to attempt when harvesting a URL
RDF_FORMATS = [
    "application/ld+json",
    "text/turtle",
    "application/rdf+xml",
    "application/n-triples",
    "text/html",
]


@contextlib.contextmanager
def capture_output():
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


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
        "formats": os.environ.get("TEST_RDF-FORMATS", ",".join(RDF_FORMATS)).split(","),
        "providence": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
    }


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


def run_harvest_test(url, formats):
    """Attempt to harvest RDF data from a URL. Returns a result dict."""
    start = time.time()
    failure_message = None
    failure_text = None
    error = None
    properties = {"urls": url}

    with capture_output() as (out, err):
        print(f"Harvesting URL: {url}")
        print(f"Formats attempted: {formats}")
        try:
            graph = get_graph_for_format(url, formats)
            if graph is None:
                print(f"No RDF graph returned for {url}", file=sys.stderr)
                failure_message = "No RDF graph could be harvested"
                failure_text = f"get_graph_for_format returned None for {url}"
            elif len(graph) == 0:
                print(f"Empty RDF graph harvested from {url}", file=sys.stderr)
                failure_message = "Empty RDF graph harvested"
                failure_text = f"RDF graph contained 0 triples for {url}"
            else:
                triple_count = len(graph)
                print(f"OK: harvested {triple_count} triple(s) from {url}")
                properties["triple_count"] = str(triple_count)
        except Exception as e:
            elapsed = time.time() - start
            print(f"Exception harvesting {url}: {e}", file=sys.stderr)
            error = str(e)

    duration = time.time() - start

    return {
        "case_name": f"semantic_harvest [{url}]",
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


def create_junit_report(suite_name, results, output_file, special_key_append_properties, providence):
    suite = TestSuite(suite_name)
    suite.timestamp = datetime.now(timezone.utc).isoformat()
    total_time = 0.0
    added_properties = set()
    append_properties = {}  # key -> list of values to be appended

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
        normalized_values = [str(v) for v in values if v is not None and str(v) != ""]
        if normalized_values:
            suite.add_property(key, ", ".join(normalized_values))

    suite.add_property("providence", providence)
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "semantic-harvest")
    config = parse_config()

    if not config["urls"]:
        results = [skipped_test("semantic_harvest", "No URL(s) configured")]
    else:
        results = []
        for url in config["urls"]:
            results.append(run_harvest_test(url, config["formats"]))

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(
        suite_name,
        results,
        output_file=report_path,
        special_key_append_properties={"urls"},
        providence=config["providence"],
    )
