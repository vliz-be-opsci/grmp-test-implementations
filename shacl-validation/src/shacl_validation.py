#!/usr/bin/env python3
"""
SHACL Validation Test
Harvests RDF graphs from data URLs and validates them against a SHACL shapes
graph, then writes a JUnit XML report.
"""

import ast
import contextlib
import io
import os
import sys
import time
from datetime import datetime, timezone

from junitparser import Error, Failure, JUnitXml, Skipped, TestCase, TestSuite
from pyshacl import validate
from sema.harvest import url_to_graph


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
    raw_urls = os.environ.get("TEST_DATA_URLS", "[]")
    try:
        parsed_urls = ast.literal_eval(raw_urls)
    except (ValueError, SyntaxError):
        parsed_urls = []

    if isinstance(parsed_urls, str):
        parsed_urls = [parsed_urls]
    elif not isinstance(parsed_urls, (list, tuple)):
        raise ValueError("TEST_DATA_URLS must be a URL string or list/tuple of URL strings")

    data_urls = [u for u in parsed_urls if isinstance(u, str) and u]

    return {
        "data_urls": data_urls,
        "shapes_url": os.environ.get("TEST_SHAPES_URL", ""),
        "timeout": _parse_int_env("TEST_TIMEOUT", 30, minimum=1),
        "providence": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
    }


def harvest_graph(url):
    """Harvest a URL into an rdflib Graph. Returns (graph, error)."""
    try:
        graph = url_to_graph(url)
        return graph, None
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


def run_shacl_test(data_url, shapes_graph):
    """Harvest data_url and validate it against shapes_graph."""
    failure_message = None
    failure_text = None
    error = None
    properties = {"data_urls": data_url}

    start = time.time()
    with capture_output() as (out, err):
        print(f"Harvesting data graph from: {data_url}")
        data_graph, harvest_error = harvest_graph(data_url)

        if harvest_error:
            print(f"Failed to harvest data graph: {harvest_error}", file=sys.stderr)
            error = f"Could not harvest data graph: {harvest_error}"
        else:
            print(f"Harvested {len(data_graph)} triples")
            print("Running SHACL validation...")
            try:
                conforms, _results_graph, results_text = validate(
                    data_graph, shacl_graph=shapes_graph
                )
                if conforms:
                    print("SHACL validation passed: data graph conforms to shapes")
                else:
                    print("SHACL validation failed: data graph does not conform", file=sys.stderr)
                    failure_message = "SHACL validation failed"
                    failure_text = results_text
            except Exception as e:
                print(f"SHACL validation error: {e}", file=sys.stderr)
                error = f"SHACL validation error: {e}"

    duration = time.time() - start

    return {
        "case_name": f"shacl_validation [{data_url}]",
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


def create_junit_report(suite_name, results, output_file, shapes_url, providence):
    suite = TestSuite(suite_name)
    suite.timestamp = datetime.now(timezone.utc).isoformat()
    total_time = 0.0
    append_data_urls = []

    for result in results:
        case = TestCase(result["case_name"], classname=suite_name)
        case.time = result["duration"]
        total_time += result["duration"]

        data_url = result["properties"].get("data_urls")
        if data_url:
            append_data_urls.append(data_url)

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

    if shapes_url:
        suite.add_property("shapes_url", shapes_url)
    if append_data_urls:
        suite.add_property("data_urls", ", ".join(append_data_urls))
    suite.add_property("providence", providence)
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "shacl-validation")
    config = parse_config()

    if not config["data_urls"] or not config["shapes_url"]:
        results = [skipped_test("shacl_validation", "No data_urls or shapes_url configured")]
        shapes_url = config.get("shapes_url", "")
    else:
        # Harvest shapes graph once
        shapes_url = config["shapes_url"]
        print(f"Harvesting shapes graph from: {shapes_url}")
        shapes_graph, shapes_error = harvest_graph(shapes_url)
        if shapes_error:
            print(f"Error harvesting shapes graph: {shapes_error}", file=sys.stderr)
            sys.exit(1)
        print(f"Harvested shapes graph with {len(shapes_graph)} triples")

        results = []
        for url in config["data_urls"]:
            results.append(run_shacl_test(url, shapes_graph))

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(
        suite_name,
        results,
        output_file=report_path,
        shapes_url=shapes_url,
        providence=config["providence"],
    )
