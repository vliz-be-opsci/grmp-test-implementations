#!/usr/bin/env python3
"""
Unit tests for ldes_validation.py

Run with (from ldes-validation/ root):
    pip install -r requirements-dev.txt
    PYTHONPATH=src pytest tests/test_ldes_validation.py -v
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from rdflib import Graph, Namespace, RDF, URIRef

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ldes_validation import (
    _detect_rdf_format,
    create_junit_report,
    fetch_rdf_graph,
    fetch_shapes_graph,
    parse_config,
    run_ldes_validation,
    skipped_test,
)

LDES = Namespace("https://w3id.org/ldes#")
TREE = Namespace("https://w3id.org/tree#")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_graph(triples=None):
    """Return an rdflib.Graph with the given list of (s, p, o) tuples."""
    g = Graph()
    for s, p, o in (triples or []):
        g.add((s, p, o))
    return g


def ldes_graph_with_view():
    """Minimal LDES graph: one EventStream with one tree:view."""
    stream = URIRef("https://example.org/stream")
    view = URIRef("https://example.org/stream/view")
    g = Graph()
    g.add((stream, RDF.type, LDES.EventStream))
    g.add((stream, TREE.view, view))
    return g


def ldes_graph_no_view():
    """LDES graph with EventStream but no tree:view."""
    stream = URIRef("https://example.org/stream")
    g = Graph()
    g.add((stream, RDF.type, LDES.EventStream))
    return g


def plain_rdf_graph():
    """RDF graph that is not an LDES."""
    s = URIRef("https://example.org/subject")
    p = URIRef("https://example.org/predicate")
    o = URIRef("https://example.org/object")
    g = Graph()
    g.add((s, p, o))
    return g


def ldes_graph_with_members_and_fragments():
    """LDES graph with EventStream, tree:view, members, and a child fragment."""
    stream = URIRef("https://example.org/stream")
    view = URIRef("https://example.org/stream/view")
    child = URIRef("https://example.org/stream/page2")
    member1 = URIRef("https://example.org/member/1")
    member2 = URIRef("https://example.org/member/2")
    g = Graph()
    g.add((stream, RDF.type, LDES.EventStream))
    g.add((stream, TREE.view, view))
    g.add((stream, LDES.member, member1))
    g.add((stream, LDES.member, member2))
    g.add((view, TREE.node, child))
    return g


# ---------------------------------------------------------------------------
# _detect_rdf_format
# ---------------------------------------------------------------------------


class TestDetectRdfFormat:
    def test_turtle_content_type(self):
        assert _detect_rdf_format("text/turtle; charset=utf-8", "") == "turtle"

    def test_jsonld_content_type(self):
        assert _detect_rdf_format("application/ld+json", "") == "json-ld"

    def test_rdfxml_content_type(self):
        assert _detect_rdf_format("application/rdf+xml", "") == "xml"

    def test_ttl_extension_fallback(self):
        assert _detect_rdf_format("", "https://example.org/data.ttl") == "turtle"

    def test_jsonld_extension_fallback(self):
        assert _detect_rdf_format("", "https://example.org/data.jsonld") == "json-ld"

    def test_rdf_extension_fallback(self):
        assert _detect_rdf_format("", "https://example.org/data.rdf") == "xml"

    def test_nt_extension_fallback(self):
        assert _detect_rdf_format("", "https://example.org/data.nt") == "nt"

    def test_default_turtle(self):
        assert _detect_rdf_format("", "https://example.org/data") == "turtle"

    def test_content_type_takes_priority_over_extension(self):
        assert (
            _detect_rdf_format(
                "application/ld+json", "https://example.org/data.ttl"
            )
            == "json-ld"
        )

    def test_query_string_stripped(self):
        assert (
            _detect_rdf_format("", "https://example.org/data.ttl?v=1") == "turtle"
        )


# ---------------------------------------------------------------------------
# parse_config
# ---------------------------------------------------------------------------


class TestParseConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("TEST_URLS", raising=False)
        monkeypatch.delenv("TEST_TIMEOUT", raising=False)
        monkeypatch.delenv("TEST_MIN-MEMBERS", raising=False)
        monkeypatch.delenv("TEST_MIN-FRAGMENTS", raising=False)
        monkeypatch.delenv("TEST_SHAPES-URL", raising=False)
        monkeypatch.delenv("SPECIAL_SOURCE_FILE", raising=False)
        monkeypatch.delenv("SPECIAL_CREATE_ISSUE", raising=False)
        config = parse_config()
        assert config["urls"] == []
        assert config["timeout"] == 30
        assert config["min_members"] == 0
        assert config["min_fragments"] == 0
        assert config["shapes_url"] == ""
        assert config["provenance"] == "unknown"
        assert config["create_issue"] is False

    def test_single_url_string(self, monkeypatch):
        monkeypatch.setenv("TEST_URLS", "'https://example.org/stream'")
        config = parse_config()
        assert config["urls"] == ["https://example.org/stream"]

    def test_list_of_urls(self, monkeypatch):
        monkeypatch.setenv(
            "TEST_URLS",
            "['https://example.org/stream1', 'https://example.org/stream2']",
        )
        config = parse_config()
        assert config["urls"] == [
            "https://example.org/stream1",
            "https://example.org/stream2",
        ]

    def test_invalid_urls_env(self, monkeypatch):
        monkeypatch.setenv("TEST_URLS", "not valid python")
        config = parse_config()
        assert config["urls"] == []

    def test_timeout_override(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "60")
        config = parse_config()
        assert config["timeout"] == 60

    def test_timeout_below_minimum_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "0")
        config = parse_config()
        assert config["timeout"] == 30

    def test_timeout_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_TIMEOUT", "abc")
        config = parse_config()
        assert config["timeout"] == 30

    def test_min_members_override(self, monkeypatch):
        monkeypatch.setenv("TEST_MIN-MEMBERS", "5")
        config = parse_config()
        assert config["min_members"] == 5

    def test_min_members_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_MIN-MEMBERS", "abc")
        config = parse_config()
        assert config["min_members"] == 0

    def test_min_fragments_override(self, monkeypatch):
        monkeypatch.setenv("TEST_MIN-FRAGMENTS", "3")
        config = parse_config()
        assert config["min_fragments"] == 3

    def test_min_fragments_invalid_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_MIN-FRAGMENTS", "abc")
        config = parse_config()
        assert config["min_fragments"] == 0

    def test_shapes_url(self, monkeypatch):
        monkeypatch.setenv("TEST_SHAPES-URL", "https://example.org/shapes.ttl")
        config = parse_config()
        assert config["shapes_url"] == "https://example.org/shapes.ttl"

    def test_provenance(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "my_source.yaml")
        config = parse_config()
        assert config["provenance"] == "my_source.yaml"

    def test_create_issue_true(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_CREATE_ISSUE", "true")
        config = parse_config()
        assert config["create_issue"] is True

    def test_create_issue_false(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_CREATE_ISSUE", "false")
        config = parse_config()
        assert config["create_issue"] is False


# ---------------------------------------------------------------------------
# fetch_rdf_graph / fetch_shapes_graph
# ---------------------------------------------------------------------------


class TestFetchRdfGraph:
    def _mock_response(self, status_code=200, content_type="text/turtle", text=""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"Content-Type": content_type}
        resp.text = text
        resp.raise_for_status = MagicMock()
        return resp

    def test_success_turtle(self):
        turtle = (
            "@prefix ldes: <https://w3id.org/ldes#> .\n"
            "@prefix tree: <https://w3id.org/tree#> .\n"
            "<https://example.org/stream> a ldes:EventStream ;\n"
            "    tree:view <https://example.org/stream/view> .\n"
        )
        resp = self._mock_response(content_type="text/turtle", text=turtle)
        with patch("ldes_validation.requests.get", return_value=resp):
            g, error = fetch_rdf_graph("https://example.org/stream")
        assert error is None
        assert g is not None
        assert len(g) > 0

    def test_http_error(self):
        resp = self._mock_response(status_code=404)
        resp.raise_for_status.side_effect = Exception("404 Not Found")
        with patch("ldes_validation.requests.get", return_value=resp):
            g, error = fetch_rdf_graph("https://example.org/missing")
        assert g is None
        assert error is not None

    def test_network_error(self):
        with patch(
            "ldes_validation.requests.get", side_effect=Exception("Connection refused")
        ):
            g, error = fetch_rdf_graph("https://example.org/stream")
        assert g is None
        assert "Connection refused" in error

    def test_parse_error(self):
        resp = self._mock_response(content_type="text/turtle", text="<unclosed URI without angle bracket")
        with patch("ldes_validation.requests.get", return_value=resp):
            g, error = fetch_rdf_graph("https://example.org/stream")
        assert g is None
        assert error is not None


class TestFetchShapesGraph:
    def test_delegates_to_fetch_rdf_graph(self):
        shapes_graph = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])
        with patch("ldes_validation.fetch_rdf_graph", return_value=(shapes_graph, None)) as mock_fetch:
            g, error = fetch_shapes_graph("https://example.org/shapes.ttl", timeout=15)
        mock_fetch.assert_called_once_with("https://example.org/shapes.ttl", timeout=15)
        assert error is None
        assert g is shapes_graph


# ---------------------------------------------------------------------------
# run_ldes_validation
# ---------------------------------------------------------------------------


class TestRunLdesValidation:
    URL = "https://example.org/stream"

    def test_valid_ldes_all_pass(self):
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL)
        assert len(results) == 3
        harvest, event_stream, tree_view = results
        assert harvest["failure_message"] is None
        assert harvest["error"] is None
        assert event_stream["failure_message"] is None
        assert event_stream["error"] is None
        assert tree_view["failure_message"] is None
        assert tree_view["error"] is None

    def test_harvest_failure_skips_remaining(self):
        with patch(
            "ldes_validation.fetch_rdf_graph", return_value=(None, "network timeout")
        ):
            results = run_ldes_validation(self.URL)
        assert len(results) == 3
        harvest, event_stream, tree_view = results
        assert harvest["failure_message"] is not None
        assert event_stream["skipped"] is True
        assert tree_view["skipped"] is True

    def test_harvest_failure_skips_optional_tests(self):
        shapes = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])
        with patch(
            "ldes_validation.fetch_rdf_graph", return_value=(None, "network timeout")
        ):
            results = run_ldes_validation(
                self.URL, min_members=1, min_fragments=1, shapes_graph=shapes
            )
        assert len(results) == 6
        assert all(r["skipped"] for r in results[1:])

    def test_no_event_stream_skips_tree_view(self):
        graph = plain_rdf_graph()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL)
        assert len(results) == 3
        harvest, event_stream, tree_view = results
        assert harvest["failure_message"] is None
        assert event_stream["failure_message"] == "No ldes:EventStream declaration found"
        assert tree_view["skipped"] is True
        assert "No ldes:EventStream found" in tree_view["skipped_message"]

    def test_no_event_stream_skips_optional_tests(self):
        graph = plain_rdf_graph()
        shapes = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(
                self.URL, min_members=1, min_fragments=1, shapes_graph=shapes
            )
        assert len(results) == 6
        assert results[2]["skipped"] is True  # ldes_tree_view
        assert results[3]["skipped"] is True  # ldes_min_members
        assert results[4]["skipped"] is True  # ldes_min_fragments
        assert results[5]["skipped"] is True  # ldes_member_shacl

    def test_event_stream_no_tree_view(self):
        graph = ldes_graph_no_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL)
        assert len(results) == 3
        harvest, event_stream, tree_view = results
        assert harvest["failure_message"] is None
        assert event_stream["failure_message"] is None
        assert tree_view["failure_message"] == "No tree:view relation found"

    def test_case_names_contain_url(self):
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL)
        for result in results:
            assert self.URL in result["case_name"]

    def test_url_in_properties(self):
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL)
        for result in results:
            if not result["skipped"]:
                assert result["properties"].get("urls") == self.URL

    # ------------------------------------------------------------------
    # min_members tests
    # ------------------------------------------------------------------

    def test_min_members_not_checked_when_zero(self):
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, min_members=0)
        # Only 3 base results, no min_members case
        assert len(results) == 3
        assert not any("ldes_min_members" in r["case_name"] for r in results)

    def test_min_members_passes_when_sufficient(self):
        graph = ldes_graph_with_members_and_fragments()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, min_members=2)
        min_members_result = next(
            r for r in results if "ldes_min_members" in r["case_name"]
        )
        assert min_members_result["failure_message"] is None
        assert min_members_result["error"] is None

    def test_min_members_fails_when_insufficient(self):
        graph = ldes_graph_with_view()  # no members
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, min_members=1)
        min_members_result = next(
            r for r in results if "ldes_min_members" in r["case_name"]
        )
        assert min_members_result["failure_message"] is not None
        assert "0" in min_members_result["failure_message"]

    # ------------------------------------------------------------------
    # min_fragments tests
    # ------------------------------------------------------------------

    def test_min_fragments_not_checked_when_zero(self):
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, min_fragments=0)
        assert not any("ldes_min_fragments" in r["case_name"] for r in results)

    def test_min_fragments_passes_when_sufficient(self):
        graph = ldes_graph_with_members_and_fragments()
        # has 1 tree:view node + 1 tree:node child = 2 distinct fragments
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, min_fragments=2)
        min_fragments_result = next(
            r for r in results if "ldes_min_fragments" in r["case_name"]
        )
        assert min_fragments_result["failure_message"] is None

    def test_min_fragments_fails_when_insufficient(self):
        graph = ldes_graph_with_view()  # only 1 fragment (root view node)
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, min_fragments=5)
        min_fragments_result = next(
            r for r in results if "ldes_min_fragments" in r["case_name"]
        )
        assert min_fragments_result["failure_message"] is not None

    # ------------------------------------------------------------------
    # SHACL member validation tests
    # ------------------------------------------------------------------

    def test_member_shacl_not_checked_when_no_shapes_graph(self):
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, shapes_graph=None)
        assert not any("ldes_member_shacl" in r["case_name"] for r in results)

    def test_member_shacl_passes_when_conforms(self):
        graph = ldes_graph_with_view()
        shapes_graph = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.shacl_validate", return_value=(True, None, "")):
            results = run_ldes_validation(self.URL, shapes_graph=shapes_graph)
        shacl_result = next(
            r for r in results if "ldes_member_shacl" in r["case_name"]
        )
        assert shacl_result["failure_message"] is None
        assert shacl_result["error"] is None

    def test_member_shacl_fails_when_not_conforms(self):
        graph = ldes_graph_with_view()
        shapes_graph = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])
        report_text = "Constraint violation"
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.shacl_validate", return_value=(False, None, report_text)):
            results = run_ldes_validation(self.URL, shapes_graph=shapes_graph)
        shacl_result = next(
            r for r in results if "ldes_member_shacl" in r["case_name"]
        )
        assert shacl_result["failure_message"] == "SHACL validation failed"
        assert shacl_result["failure_text"] == report_text

    def test_member_shacl_error_when_exception(self):
        graph = ldes_graph_with_view()
        shapes_graph = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.shacl_validate", side_effect=Exception("pyshacl error")):
            results = run_ldes_validation(self.URL, shapes_graph=shapes_graph)
        shacl_result = next(
            r for r in results if "ldes_member_shacl" in r["case_name"]
        )
        assert shacl_result["error"] is not None
        assert "pyshacl error" in shacl_result["error"]


# ---------------------------------------------------------------------------
# skipped_test
# ---------------------------------------------------------------------------


class TestSkippedTest:
    def test_structure(self):
        result = skipped_test("my_test", "reason here")
        assert result["case_name"] == "my_test"
        assert result["skipped"] is True
        assert result["skipped_message"] == "reason here"
        assert result["failure_message"] is None
        assert result["error"] is None
        assert result["duration"] == 0.0


# ---------------------------------------------------------------------------
# create_junit_report
# ---------------------------------------------------------------------------


class TestCreateJunitReport:
    def _write_and_parse(self, results, provenance="test-prov", suite_properties=None):
        from junitparser import JUnitXml

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        try:
            create_junit_report(
                "ldes-validation",
                results,
                output_file=path,
                provenance=provenance,
                suite_properties=suite_properties,
            )
            xml = JUnitXml.fromfile(path)
            return list(xml)
        finally:
            os.unlink(path)

    def _passing_result(self, url="https://example.org/stream", case="ldes_harvest"):
        return {
            "case_name": f"{case} [{url}]",
            "duration": 0.5,
            "error": None,
            "failure_message": None,
            "failure_text": None,
            "properties": {"urls": url},
            "skipped": False,
            "skipped_message": "",
            "stdout": "OK",
            "stderr": "",
        }

    def test_passing_test(self):
        results = [self._passing_result()]
        suites = self._write_and_parse(results)
        assert len(suites) == 1
        cases = list(suites[0])
        assert len(cases) == 1
        assert cases[0].result == [] or cases[0].result is None or all(
            r is None for r in cases[0].result
        )

    def test_failing_test(self):
        from junitparser import Failure

        result = self._passing_result()
        result["failure_message"] = "No ldes:EventStream declaration found"
        result["failure_text"] = "Details here"
        suites = self._write_and_parse([result])
        cases = list(suites[0])
        assert any(isinstance(r, Failure) for r in cases[0].result)

    def test_error_test(self):
        from junitparser import Error

        result = self._passing_result()
        result["error"] = "Unexpected exception"
        suites = self._write_and_parse([result])
        cases = list(suites[0])
        assert any(isinstance(r, Error) for r in cases[0].result)

    def test_skipped_test(self):
        from junitparser import Skipped

        results = [skipped_test("ldes_validation", "No config")]
        suites = self._write_and_parse(results)
        cases = list(suites[0])
        assert any(isinstance(r, Skipped) for r in cases[0].result)

    def test_urls_property(self):
        url = "https://example.org/stream"
        results = [self._passing_result(url=url)]
        suites = self._write_and_parse(results)
        props = {p.name: p.value for p in suites[0].properties()}
        assert "urls" in props
        assert url in props["urls"]

    def test_deduplicates_urls(self):
        url = "https://example.org/stream"
        results = [
            self._passing_result(url=url, case="ldes_harvest"),
            self._passing_result(url=url, case="ldes_event_stream"),
            self._passing_result(url=url, case="ldes_tree_view"),
        ]
        suites = self._write_and_parse(results)
        props = {p.name: p.value for p in suites[0].properties()}
        assert props["urls"].count(url) == 1

    def test_provenance_property(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(results, provenance="my_file.yaml")
        props = {p.name: p.value for p in suites[0].properties()}
        assert props.get("provenance") == "my_file.yaml"

    def test_create_issue_property(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results, suite_properties={"create_issue": True}
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert props.get("create-issue") == "true"

    def test_shapes_url_property_when_set(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results,
            suite_properties={"shapes_url": "https://example.org/shapes.ttl"},
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert props.get("shapes_url") == "https://example.org/shapes.ttl"

    def test_shapes_url_property_not_added_when_empty(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results,
            suite_properties={"shapes_url": ""},
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert "shapes_url" not in props

    def test_min_members_property_when_set(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results,
            suite_properties={"min_members": 5, "min_fragments": 0},
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert props.get("min_members") == "5"

    def test_min_fragments_property_when_set(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results,
            suite_properties={"min_members": 0, "min_fragments": 3},
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert props.get("min_fragments") == "3"

    def test_min_members_property_not_added_when_zero(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results,
            suite_properties={"min_members": 0},
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert "min_members" not in props

