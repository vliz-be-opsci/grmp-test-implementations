#!/usr/bin/env python3
"""
LDES Validation Test
Fetches RDF graphs from one or more URLs and validates them as Linked Data
Event Streams (LDES), checking for ldes:EventStream declarations, tree:view
relations, minimum member and fragment counts, and optional SHACL validation
of retrieved members, then writes a JUnit XML report.
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
from pyshacl import validate as shacl_validate
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
        "min_members": _parse_int_env("TEST_MIN-MEMBERS", 0, minimum=0),
        "min_fragments": _parse_int_env("TEST_MIN-FRAGMENTS", 0, minimum=0),
        "shapes_url": os.environ.get("TEST_SHAPES-URL", ""),
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


def fetch_shapes_graph(url, timeout=30):
    """Fetch a SHACL shapes graph from a URL. Returns (graph, error_string)."""
    print(f"Fetching SHACL shapes graph from: {url}")
    return fetch_rdf_graph(url, timeout=timeout)


def traverse_ldes_feed(root_url, root_graph, timeout=30):
    """
    Traverse an LDES feed by following tree:node links discovered via
    tree:Relation nodes.  Starting from the tree:view targets declared in
    root_graph, each linked fragment page is fetched and its own tree:node
    links are followed recursively.  A visited-set prevents infinite loops.

    Returns:
        merged_graph   – rdflib.Graph merging all successfully visited pages
        traversed_urls – set of page URLs successfully fetched (including root)
        errors         – list of (url, error_string) for pages that could not
                         be fetched or parsed
    """
    visited = {root_url}
    merged = Graph()
    for triple in root_graph:
        merged.add(triple)
    traversed_urls = {root_url}

    # Seed the queue with tree:view targets declared in the root page
    queue = []
    for view_node in root_graph.objects(predicate=TREE.view):
        candidate = str(view_node)
        if candidate not in visited:
            queue.append(candidate)

    errors = []
    while queue:
        fragment_url = queue.pop(0)
        if fragment_url in visited:
            continue
        visited.add(fragment_url)

        print(f"Fetching LDES fragment: {fragment_url}")
        page_graph, error = fetch_rdf_graph(fragment_url, timeout=timeout)
        if error:
            print(
                f"Could not fetch fragment {fragment_url}: {error}",
                file=sys.stderr,
            )
            errors.append((fragment_url, error))
            continue

        traversed_urls.add(fragment_url)
        for triple in page_graph:
            merged.add(triple)

        # Discover child fragments via tree:node predicates
        for child_node in page_graph.objects(predicate=TREE.node):
            child_url = str(child_node)
            if child_url not in visited:
                queue.append(child_url)

    return merged, traversed_urls, errors


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


def run_ldes_validation(url, timeout=30, min_members=0, min_fragments=0, shapes_graph=None):
    """
    Validate a URL as an LDES event stream.

    Returns a list of result dicts (3 to 6 depending on configuration):
    1. ldes_harvest         - can the URL be fetched and parsed as RDF?
    2. ldes_event_stream    - does the graph declare an ldes:EventStream?
    3. ldes_tree_view       - does the event stream expose a tree:view?
    4. ldes_min_members     - does the stream (across all traversed fragments)
                              expose >= min_members ldes:member triples?
                              (only when min_members > 0)
    5. ldes_min_fragments   - were at least min_fragments fragment pages
                              reached by following tree:Relation links?
                              (only when min_fragments > 0)
    6. ldes_member_shacl    - do the members (across all traversed fragments)
                              conform to the SHACL shapes graph?
                              (only when shapes_graph is provided)

    Optional checks (4-6) traverse the full LDES feed via tree:node links
    before evaluating.
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
        if min_members > 0:
            results.append(
                skipped_test(f"ldes_min_members [{url}]", "RDF harvest failed")
            )
        if min_fragments > 0:
            results.append(
                skipped_test(f"ldes_min_fragments [{url}]", "RDF harvest failed")
            )
        if shapes_graph is not None:
            results.append(
                skipped_test(f"ldes_member_shacl [{url}]", "RDF harvest failed")
            )
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
        if min_members > 0:
            results.append(
                skipped_test(f"ldes_min_members [{url}]", "No ldes:EventStream found")
            )
        if min_fragments > 0:
            results.append(
                skipped_test(
                    f"ldes_min_fragments [{url}]", "No ldes:EventStream found"
                )
            )
        if shapes_graph is not None:
            results.append(
                skipped_test(
                    f"ldes_member_shacl [{url}]", "No ldes:EventStream found"
                )
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

    # ------------------------------------------------------------------
    # Traverse the full feed for optional checks
    # ------------------------------------------------------------------
    needs_traversal = (
        min_members > 0 or min_fragments > 0 or shapes_graph is not None
    )
    if needs_traversal:
        with capture_output() as (trav_out, trav_err):
            print(f"Traversing LDES feed from: {url}")
            merged_graph, traversed_urls, traverse_errors = traverse_ldes_feed(
                url, graph, timeout=timeout
            )
            print(
                f"Traversal complete: {len(traversed_urls)} fragment(s) fetched, "
                f"{len(merged_graph)} total triple(s)"
            )
            if traverse_errors:
                for frag_url, frag_err in traverse_errors:
                    print(
                        f"Warning: could not fetch fragment {frag_url}: {frag_err}",
                        file=sys.stderr,
                    )
        traversal_stdout = trav_out.getvalue()
        traversal_stderr = trav_err.getvalue()
    else:
        merged_graph = graph
        traversed_urls = {url}
        traversal_stdout = ""
        traversal_stderr = ""

    # ------------------------------------------------------------------
    # Test 4: minimum member count (optional)
    # ------------------------------------------------------------------
    if min_members > 0:
        start = time.time()
        with capture_output() as (out, err):
            # Re-query event streams from merged_graph so that EventStream
            # declarations in child fragments are also honoured.
            all_streams = list(merged_graph.subjects(RDF.type, LDES.EventStream))
            members = set()
            for es in all_streams:
                members.update(merged_graph.objects(es, LDES.member))
            member_count = len(members)
            print(
                f"Found {member_count} ldes:member(s) across "
                f"{len(traversed_urls)} traversed fragment(s); "
                f"required minimum: {min_members}"
            )
            if member_count < min_members:
                print(
                    f"Insufficient members: {member_count} < {min_members}",
                    file=sys.stderr,
                )

        min_members_duration = time.time() - start
        results.append(
            {
                "case_name": f"ldes_min_members [{url}]",
                "duration": min_members_duration,
                "error": None,
                "failure_message": (
                    f"Insufficient members: found {member_count}, "
                    f"expected at least {min_members}"
                    if member_count < min_members
                    else None
                ),
                "failure_text": (
                    f"The event stream at {url} exposes only {member_count} "
                    f"ldes:member triple(s) across {len(traversed_urls)} "
                    f"traversed fragment(s), but at least {min_members} "
                    "are required"
                    if member_count < min_members
                    else None
                ),
                "properties": {"urls": url},
                "skipped": False,
                "skipped_message": "",
                "stdout": traversal_stdout + out.getvalue(),
                "stderr": traversal_stderr + err.getvalue(),
            }
        )

    # ------------------------------------------------------------------
    # Test 5: minimum fragment count (optional)
    # ------------------------------------------------------------------
    if min_fragments > 0:
        start = time.time()
        with capture_output() as (out, err):
            fragment_count = len(traversed_urls)
            print(
                f"Traversed {fragment_count} LDES fragment(s) "
                f"(following tree:Relation → tree:node links); "
                f"required minimum: {min_fragments}"
            )
            for frag in sorted(traversed_urls):
                print(f"  fragment: {frag}")
            if fragment_count < min_fragments:
                print(
                    f"Insufficient fragments: {fragment_count} < {min_fragments}",
                    file=sys.stderr,
                )

        min_fragments_duration = time.time() - start
        results.append(
            {
                "case_name": f"ldes_min_fragments [{url}]",
                "duration": min_fragments_duration,
                "error": None,
                "failure_message": (
                    f"Insufficient fragments: traversed {fragment_count}, "
                    f"expected at least {min_fragments}"
                    if fragment_count < min_fragments
                    else None
                ),
                "failure_text": (
                    f"The LDES feed at {url} yielded only {fragment_count} "
                    f"traversed fragment(s) (following tree:Relation → "
                    f"tree:node links), but at least {min_fragments} "
                    "are required"
                    if fragment_count < min_fragments
                    else None
                ),
                "properties": {"urls": url},
                "skipped": False,
                "skipped_message": "",
                "stdout": traversal_stdout + out.getvalue(),
                "stderr": traversal_stderr + err.getvalue(),
            }
        )

    # ------------------------------------------------------------------
    # Test 6: SHACL validation of LDES members (optional)
    # ------------------------------------------------------------------
    if shapes_graph is not None:
        start = time.time()
        shacl_error = None
        with capture_output() as (out, err):
            print(
                f"Running SHACL validation against members from "
                f"{len(traversed_urls)} traversed fragment(s) of: {url}"
            )
            try:
                conforms, _results_graph, results_text = shacl_validate(
                    merged_graph, shacl_graph=shapes_graph
                )
                if conforms:
                    print("SHACL validation passed: members conform to shapes")
                else:
                    print(
                        "SHACL validation failed: members do not conform to shapes",
                        file=sys.stderr,
                    )
            except Exception as e:
                print(f"SHACL validation error: {e}", file=sys.stderr)
                shacl_error = str(e)
                conforms = None
                results_text = ""

        shacl_duration = time.time() - start
        results.append(
            {
                "case_name": f"ldes_member_shacl [{url}]",
                "duration": shacl_duration,
                "error": shacl_error,
                "failure_message": (
                    "SHACL validation failed"
                    if shacl_error is None and conforms is False
                    else None
                ),
                "failure_text": (
                    results_text
                    if shacl_error is None and conforms is False
                    else None
                ),
                "properties": {"urls": url},
                "skipped": False,
                "skipped_message": "",
                "stdout": traversal_stdout + out.getvalue(),
                "stderr": traversal_stderr + err.getvalue(),
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
    # provenance is always included regardless of suite_properties
    suite.add_property("provenance", provenance)
    if suite_properties is not None:
        if suite_properties.get("shapes_url"):
            suite.add_property("shapes_url", suite_properties["shapes_url"])
        if suite_properties.get("min_members", 0) > 0:
            suite.add_property("min_members", str(suite_properties["min_members"]))
        if suite_properties.get("min_fragments", 0) > 0:
            suite.add_property(
                "min_fragments", str(suite_properties["min_fragments"])
            )
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

    shapes_graph = None
    if config["shapes_url"]:
        shapes_graph, shapes_error = fetch_shapes_graph(
            config["shapes_url"], timeout=config["timeout"]
        )
        if shapes_error:
            print(
                f"Error fetching SHACL shapes graph: {shapes_error}",
                file=sys.stderr,
            )
            sys.exit(1)
        print(
            f"Fetched shapes graph with {len(shapes_graph)} triple(s)"
        )

    if not config["urls"]:
        results = [skipped_test("ldes_validation", "No URL(s) configured")]
    else:
        results = []
        for url in config["urls"]:
            results.extend(
                run_ldes_validation(
                    url,
                    timeout=config["timeout"],
                    min_members=config["min_members"],
                    min_fragments=config["min_fragments"],
                    shapes_graph=shapes_graph,
                )
            )

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(
        suite_name,
        results,
        output_file=report_path,
        provenance=config["provenance"],
        suite_properties=config,
    )
