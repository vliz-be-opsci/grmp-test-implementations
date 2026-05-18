#!/usr/bin/env python3
"""
WRX Test
Harvest RDF for one or more URLs using wrx (JavaScript), parse again in Python,
and assert a minimum triple count per URL.
"""

import ast
import contextlib
import io
import json
import os
import subprocess
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import rdflib
from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped


@contextlib.contextmanager
def capture_output():
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


def _parse_list_env(name, default):
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
    print(f"Invalid {name}={raw!r}; must be a list of strings. Falling back to default", file=sys.stderr)
    return default


def _parse_int_env(name, default, *, minimum=None):
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        print(f"Invalid {name}={raw!r}; falling back to {default}", file=sys.stderr)
        return default
    if minimum is not None and value < minimum:
        print(f"Invalid {name}={raw!r}; must be >= {minimum}. Falling back to {default}", file=sys.stderr)
        return default
    return value


def parse_config():
    return {
        "urls": _parse_list_env("TEST_URLS", []),
        "min_triples": _parse_int_env("TEST_MIN-TRIPLES", 1, minimum=1),
        "provenance": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
        "create_issue": os.environ.get("SPECIAL_CREATE_ISSUE", "false").lower() == "true",
    }


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


def _run_wrx_extractor(url):
    script_path = os.path.join(os.path.dirname(__file__), "wrx_fetch.mjs")
    process = subprocess.run(
        ["node", script_path, url],
        capture_output=True,
        text=True,
        check=False,
    )

    if process.returncode != 0:
        detail = (process.stderr or process.stdout or "Unknown wrx execution error").strip()
        raise RuntimeError(detail)

    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from wrx helper: {process.stdout!r}") from exc


_RDFLIB_FORMATS = {
    "text/turtle": "turtle",
    "application/ld+json": "json-ld",
    "application/rdf+xml": "xml",
    "application/n-triples": "nt",
    "application/n-quads": "nquads",
    "application/trig": "trig",
    "text/n3": "n3",
}


def _parse_graph(rdf_content, rdf_mime):
    mime = (rdf_mime or "").split(";")[0].strip().lower()
    rdflib_format = _RDFLIB_FORMATS.get(mime)
    if rdflib_format is None:
        raise ValueError(f"Unsupported RDF media type from wrx: {rdf_mime!r}")

    graph = rdflib.Graph()
    graph.parse(data=rdf_content, format=rdflib_format)
    return graph, mime


def run_wrx_triples_test(url, min_triples):
    case_name = f"wrx_triples [{url}]"
    start = time.time()

    with capture_output() as (out, err):
        print(f"Running wrx extraction for: {url}")
        print(f"Minimum triples required: {min_triples}")

        try:
            wrx_result = _run_wrx_extractor(url)
        except Exception as exc:
            print(f"wrx subprocess failed: {exc}", file=sys.stderr)
            duration = time.time() - start
            return _result(
                case_name,
                url,
                error=f"wrx subprocess failed: {exc}",
                stdout=out.getvalue(),
                stderr=err.getvalue(),
                duration=duration,
            )

        if not wrx_result.get("ok"):
            reason = wrx_result.get("reason") or "No RDF extracted"
            print(reason)
            duration = time.time() - start
            return _result(
                case_name,
                url,
                failure_message="No RDF triples found by wrx",
                failure_text=f"URL: {url}\nReason: {reason}",
                stdout=out.getvalue(),
                stderr=err.getvalue(),
                duration=duration,
                properties={
                    "urls": url,
                    "hostnames": _hostname(url),
                    "min-triples": str(min_triples),
                },
            )

        rdf_content = wrx_result.get("content") or ""
        rdf_format = wrx_result.get("format") or ""

        try:
            graph, normalized_format = _parse_graph(rdf_content, rdf_format)
            triples_count = len(graph)
            query_rows = list(graph.query("SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1"))
            query_ok = len(query_rows) > 0
            print(f"wrx format: {normalized_format}")
            print(f"triples_found: {triples_count}")
            print(f"query_result_rows: {len(query_rows)}")
        except Exception as exc:
            print(f"Failed to parse/query RDF in Python: {exc}", file=sys.stderr)
            duration = time.time() - start
            return _result(
                case_name,
                url,
                error=f"Failed to parse/query RDF in Python: {exc}",
                stdout=out.getvalue(),
                stderr=err.getvalue(),
                duration=duration,
                properties={
                    "urls": url,
                    "hostnames": _hostname(url),
                    "min-triples": str(min_triples),
                    "wrx-format": rdf_format,
                },
            )

        failure_message = None
        failure_text = None

        if triples_count < min_triples:
            failure_message = "Insufficient triples found"
            failure_text = (
                f"URL: {url}\n"
                f"Expected at least {min_triples} triples, found {triples_count}."
            )
        elif not query_ok:
            failure_message = "SPARQL query did not resolve"
            failure_text = (
                f"URL: {url}\n"
                "Expected query SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1 to return at least one row."
            )

    duration = time.time() - start
    return _result(
        case_name,
        url,
        failure_message=failure_message,
        failure_text=failure_text,
        stdout=out.getvalue(),
        stderr=err.getvalue(),
        duration=duration,
        properties={
            "urls": url,
            "hostnames": _hostname(url),
            "min-triples": str(min_triples),
            "wrx-format": (wrx_result.get("format") or "").split(";")[0].strip().lower(),
            "triples-found": str(triples_count),
        },
    )


def run_tests_for_url(url, config):
    return [run_wrx_triples_test(url, config["min_triples"])]


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

    if (min_triples := suite_properties.get("min_triples")) is not None:
        suite.add_property("min-triples", str(min_triples))
    suite.add_property("provenance", provenance)
    suite.add_property("create-issue", str(suite_properties.get("create_issue", False)).lower())
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "wrx-test")
    config = parse_config()

    if not config["urls"]:
        results = [skipped_test("wrx_triples", "No URL(s) configured")]
    else:
        results = []
        for url in config["urls"]:
            results.extend(run_tests_for_url(url, config))

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(
        suite_name,
        results,
        output_file=report_path,
        special_key_append_properties={"urls", "hostnames"},
        provenance=config["provenance"],
        suite_properties=config,
    )
