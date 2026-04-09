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
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ldes_validation import (
    _detect_rdf_format,
    _validate_fragment_graph,
    create_junit_report,
    extract_timestamp_path,
    extract_version_of_path,
    fetch_rdf_graph,
    fetch_shapes_graph,
    find_youngest_member_timestamp,
    parse_config,
    run_ldes_validation,
    skipped_test,
    traverse_ldes_feed,
)

LDES = Namespace("https://w3id.org/ldes#")
TREE = Namespace("https://w3id.org/tree#")
DCT = Namespace("http://purl.org/dc/terms/")
PROV = Namespace("http://www.w3.org/ns/prov#")


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
    """LDES graph with EventStream, tree:view, tree:members, and a child fragment."""
    stream = URIRef("https://example.org/stream")
    view = URIRef("https://example.org/stream/view")
    child = URIRef("https://example.org/stream/page2")
    member1 = URIRef("https://example.org/member/1")
    member2 = URIRef("https://example.org/member/2")
    g = Graph()
    g.add((stream, RDF.type, LDES.EventStream))
    g.add((stream, TREE.view, view))
    g.add((stream, TREE.member, member1))
    g.add((stream, TREE.member, member2))
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
        monkeypatch.delenv("TEST_MAX-AGE-YOUNGEST-MEMBER", raising=False)
        monkeypatch.delenv("TEST_SHAPES-URL", raising=False)
        monkeypatch.delenv("TEST_FRAGMENT-SHAPES-URL", raising=False)
        monkeypatch.delenv("SPECIAL_SOURCE_FILE", raising=False)
        monkeypatch.delenv("SPECIAL_CREATE_ISSUE", raising=False)
        config = parse_config()
        assert config["urls"] == []
        assert config["timeout"] == 30
        assert config["min_members"] == 0
        assert config["min_fragments"] == 0
        assert config["max_age_youngest_member"] == 0
        assert config["shapes_url"] == ""
        assert config["fragment_shapes_url"] == ""
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

    def test_fragment_shapes_url(self, monkeypatch):
        monkeypatch.setenv("TEST_FRAGMENT-SHAPES-URL", "https://example.org/frag-shapes.ttl")
        config = parse_config()
        assert config["fragment_shapes_url"] == "https://example.org/frag-shapes.ttl"

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
        root_graph = ldes_graph_with_members_and_fragments()  # 2 members
        traversed = {self.URL, "https://example.org/stream/view"}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(root_graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(root_graph, traversed, [], {})):
            results = run_ldes_validation(self.URL, min_members=2)
        min_members_result = next(
            r for r in results if "ldes_min_members" in r["case_name"]
        )
        assert min_members_result["failure_message"] is None
        assert min_members_result["error"] is None

    def test_min_members_fails_when_insufficient(self):
        root_graph = ldes_graph_with_view()  # no members
        traversed = {self.URL, "https://example.org/stream/view"}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(root_graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(root_graph, traversed, [], {})):
            results = run_ldes_validation(self.URL, min_members=1)
        min_members_result = next(
            r for r in results if "ldes_min_members" in r["case_name"]
        )
        assert min_members_result["failure_message"] is not None
        assert "0" in min_members_result["failure_message"]

    def test_min_members_counts_across_all_traversed_fragments(self):
        """Members discovered in child fragments count towards min_members."""
        root_graph = ldes_graph_with_view()  # 0 members in root
        stream = URIRef("https://example.org/stream")
        member_a = URIRef("https://example.org/member/a")
        member_b = URIRef("https://example.org/member/b")
        merged = Graph()
        for t in root_graph:
            merged.add(t)
        merged.add((stream, TREE.member, member_a))
        merged.add((stream, TREE.member, member_b))
        traversed = {self.URL, "https://example.org/stream/view",
                     "https://example.org/stream/page2"}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(root_graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(merged, traversed, [], {})):
            results = run_ldes_validation(self.URL, min_members=2)
        min_members_result = next(
            r for r in results if "ldes_min_members" in r["case_name"]
        )
        assert min_members_result["failure_message"] is None

    # ------------------------------------------------------------------
    # min_fragments tests
    # ------------------------------------------------------------------

    def test_min_fragments_not_checked_when_zero(self):
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL, min_fragments=0)
        assert not any("ldes_min_fragments" in r["case_name"] for r in results)

    def test_min_fragments_passes_when_sufficient(self):
        root_graph = ldes_graph_with_view()
        # Simulate 3 traversed pages (root + view + child)
        traversed = {
            self.URL,
            "https://example.org/stream/view",
            "https://example.org/stream/page2",
        }
        with patch("ldes_validation.fetch_rdf_graph", return_value=(root_graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(root_graph, traversed, [], {})):
            results = run_ldes_validation(self.URL, min_fragments=3)
        min_fragments_result = next(
            r for r in results if "ldes_min_fragments" in r["case_name"]
        )
        assert min_fragments_result["failure_message"] is None

    def test_min_fragments_fails_when_insufficient(self):
        root_graph = ldes_graph_with_view()
        traversed = {self.URL}  # only root was reachable
        with patch("ldes_validation.fetch_rdf_graph", return_value=(root_graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(root_graph, traversed, [], {})):
            results = run_ldes_validation(self.URL, min_fragments=5)
        min_fragments_result = next(
            r for r in results if "ldes_min_fragments" in r["case_name"]
        )
        assert min_fragments_result["failure_message"] is not None
        assert "1" in min_fragments_result["failure_message"]

    def test_min_fragments_counts_traversed_pages_not_just_references(self):
        """Fragment count reflects actually-fetched pages, not just URIs in root graph."""
        root_graph = ldes_graph_with_members_and_fragments()
        # 3 pages actually traversed (root + view + page2)
        traversed = {
            self.URL,
            "https://example.org/stream/view",
            "https://example.org/stream/page2",
        }
        with patch("ldes_validation.fetch_rdf_graph", return_value=(root_graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(root_graph, traversed, [], {})):
            results = run_ldes_validation(self.URL, min_fragments=3)
        min_fragments_result = next(
            r for r in results if "ldes_min_fragments" in r["case_name"]
        )
        assert min_fragments_result["failure_message"] is None

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
        traversed = {self.URL}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], {})), \
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
        traversed = {self.URL}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], {})), \
             patch("ldes_validation.shacl_validate",
                   return_value=(False, None, report_text)):
            results = run_ldes_validation(self.URL, shapes_graph=shapes_graph)
        shacl_result = next(
            r for r in results if "ldes_member_shacl" in r["case_name"]
        )
        assert shacl_result["failure_message"] == "SHACL validation failed"
        assert shacl_result["failure_text"] == report_text

    def test_member_shacl_error_when_exception(self):
        graph = ldes_graph_with_view()
        shapes_graph = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])
        traversed = {self.URL}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], {})), \
             patch("ldes_validation.shacl_validate",
                   side_effect=Exception("pyshacl error")):
            results = run_ldes_validation(self.URL, shapes_graph=shapes_graph)
        shacl_result = next(
            r for r in results if "ldes_member_shacl" in r["case_name"]
        )
        assert shacl_result["error"] is not None
        assert "pyshacl error" in shacl_result["error"]

    def test_member_shacl_validates_merged_graph_from_traversal(self):
        """SHACL is run against the full merged graph, not just the root page."""
        root_graph = ldes_graph_with_view()
        stream = URIRef("https://example.org/stream")
        member = URIRef("https://example.org/member/x")
        merged = Graph()
        for t in root_graph:
            merged.add(t)
        merged.add((stream, TREE.member, member))
        traversed = {self.URL, "https://example.org/stream/view"}
        shapes_graph = make_graph([(URIRef("urn:s"), URIRef("urn:p"), URIRef("urn:o"))])

        captured_data_graph = {}

        def fake_shacl(data_graph, shacl_graph):
            captured_data_graph["g"] = data_graph
            return True, None, ""

        with patch("ldes_validation.fetch_rdf_graph", return_value=(root_graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(merged, traversed, [], {})), \
             patch("ldes_validation.shacl_validate", side_effect=fake_shacl):
            run_ldes_validation(self.URL, shapes_graph=shapes_graph)

        assert (stream, TREE.member, member) in captured_data_graph["g"]


# ---------------------------------------------------------------------------
# traverse_ldes_feed
# ---------------------------------------------------------------------------


class TestTraverseLdesFeed:
    ROOT_URL = "https://example.org/stream"
    VIEW_URL = "https://example.org/stream/view"
    CHILD_URL = "https://example.org/stream/page2"

    def test_no_view_returns_only_root(self):
        """A root graph with no tree:view means only the root is in traversed_urls."""
        root_graph = make_graph(
            [(URIRef(self.ROOT_URL), RDF.type, LDES.EventStream)]
        )
        merged, traversed, errors, frag_val = traverse_ldes_feed(self.ROOT_URL, root_graph)
        assert traversed == {self.ROOT_URL}
        assert errors == []
        assert len(merged) == len(root_graph)
        assert frag_val == {}

    def test_single_view_page_is_fetched(self):
        """tree:view target is fetched and added to traversed_urls."""
        root_graph = ldes_graph_with_view()  # tree:view → VIEW_URL
        view_graph = make_graph(
            [(URIRef(self.VIEW_URL), RDF.type, TREE.Node)]
        )

        def fetch_side_effect(url, timeout=30):
            if url == self.VIEW_URL:
                return view_graph, None
            return None, f"unexpected URL: {url}"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(self.ROOT_URL, root_graph)

        assert self.ROOT_URL in traversed
        assert self.VIEW_URL in traversed
        assert errors == []
        assert frag_val == {}

    def test_child_fragment_discovered_via_tree_node(self):
        """tree:node links in a child page are followed to discover grandchildren."""
        root_graph = ldes_graph_with_view()  # tree:view → VIEW_URL
        view_graph = make_graph(
            [(URIRef(self.VIEW_URL), TREE.node, URIRef(self.CHILD_URL))]
        )
        child_graph = make_graph(
            [(URIRef(self.CHILD_URL), RDF.type, TREE.Node)]
        )

        def fetch_side_effect(url, timeout=30):
            if url == self.VIEW_URL:
                return view_graph, None
            if url == self.CHILD_URL:
                return child_graph, None
            return None, f"unexpected URL: {url}"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(self.ROOT_URL, root_graph)

        assert traversed == {self.ROOT_URL, self.VIEW_URL, self.CHILD_URL}
        assert errors == []
        assert frag_val == {}

    def test_cycle_prevention(self):
        """A page that links back to the root or itself is never re-fetched."""
        root_graph = ldes_graph_with_view()  # tree:view → VIEW_URL
        # view page links back to root (cycle)
        view_graph = make_graph(
            [(URIRef(self.VIEW_URL), TREE.node, URIRef(self.ROOT_URL))]
        )
        fetch_count = [0]

        def fetch_side_effect(url, timeout=30):
            fetch_count[0] += 1
            if url == self.VIEW_URL:
                return view_graph, None
            return None, f"unexpected URL: {url}"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(self.ROOT_URL, root_graph)

        assert fetch_count[0] == 1  # only the view page was fetched (root already visited)
        assert self.ROOT_URL in traversed
        assert errors == []

    def test_failed_fragment_goes_to_errors_not_traversed(self):
        """A page that cannot be fetched is recorded in errors and excluded from traversed_urls."""
        root_graph = ldes_graph_with_view()  # tree:view → VIEW_URL

        def fetch_side_effect(url, timeout=30):
            return None, "connection refused"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(self.ROOT_URL, root_graph)

        assert self.VIEW_URL not in traversed
        assert self.ROOT_URL in traversed
        assert len(errors) == 1
        assert errors[0][0] == self.VIEW_URL
        assert "connection refused" in errors[0][1]
        assert frag_val == {}  # failed fragments are not validated

    def test_members_from_child_pages_merged(self):
        """tree:member triples in child pages appear in merged_graph."""
        root_graph = ldes_graph_with_view()
        stream = URIRef(self.ROOT_URL)
        member_a = URIRef("https://example.org/member/a")
        member_b = URIRef("https://example.org/member/b")

        view_graph = make_graph(
            [(URIRef(self.VIEW_URL), TREE.node, URIRef(self.CHILD_URL))]
        )
        child_graph = make_graph([
            (stream, TREE.member, member_a),
            (stream, TREE.member, member_b),
        ])

        def fetch_side_effect(url, timeout=30):
            if url == self.VIEW_URL:
                return view_graph, None
            if url == self.CHILD_URL:
                return child_graph, None
            return None, f"unexpected URL: {url}"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(self.ROOT_URL, root_graph)

        assert errors == []
        members = list(merged.objects(stream, TREE.member))
        assert member_a in members
        assert member_b in members

    def test_root_triples_present_in_merged(self):
        """Triples from the root graph are always present in merged_graph."""
        root_graph = ldes_graph_with_view()
        # No child pages (view fetch fails, so only root is traversed)

        def fetch_side_effect(url, timeout=30):
            return None, "not found"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(self.ROOT_URL, root_graph)

        for triple in root_graph:
            assert triple in merged

    def test_max_fragments_stops_traversal_early(self):
        """Traversal stops once max_fragments pages have been fetched."""
        root_graph = ldes_graph_with_view()  # tree:view → VIEW_URL
        view_graph = make_graph(
            [(URIRef(self.VIEW_URL), TREE.node, URIRef(self.CHILD_URL))]
        )
        child_graph = make_graph(
            [(URIRef(self.CHILD_URL), RDF.type, TREE.Node)]
        )
        fetch_count = [0]

        def fetch_side_effect(url, timeout=30):
            fetch_count[0] += 1
            if url == self.VIEW_URL:
                return view_graph, None
            if url == self.CHILD_URL:
                return child_graph, None
            return None, f"unexpected URL: {url}"

        # max_fragments=2 means root + VIEW_URL (2 total); CHILD_URL should not be fetched
        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(
                self.ROOT_URL, root_graph, max_fragments=2
            )

        # Should have stopped after root + VIEW_URL (2 fragments)
        assert len(traversed) == 2
        assert self.ROOT_URL in traversed
        assert self.VIEW_URL in traversed
        assert self.CHILD_URL not in traversed
        # fetch_count is 1 because only VIEW_URL was fetched (root_graph is passed as parameter)
        assert fetch_count[0] == 1

    def test_max_fragments_none_traverses_all(self):
        """max_fragments=None means the entire feed is traversed."""
        root_graph = ldes_graph_with_view()  # tree:view → VIEW_URL
        view_graph = make_graph(
            [(URIRef(self.VIEW_URL), TREE.node, URIRef(self.CHILD_URL))]
        )
        child_graph = make_graph(
            [(URIRef(self.CHILD_URL), RDF.type, TREE.Node)]
        )

        def fetch_side_effect(url, timeout=30):
            if url == self.VIEW_URL:
                return view_graph, None
            if url == self.CHILD_URL:
                return child_graph, None
            return None, f"unexpected URL: {url}"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect):
            merged, traversed, errors, frag_val = traverse_ldes_feed(
                self.ROOT_URL, root_graph, max_fragments=None
            )

        assert traversed == {self.ROOT_URL, self.VIEW_URL, self.CHILD_URL}
        assert errors == []


class TestRunLdesValidationUsesMaxFragments:
    """Verify that run_ldes_validation passes min_fragments as max_fragments."""

    URL = "https://example.org/stream"

    def test_traverse_called_with_max_fragments_when_min_fragments_set(self):
        """When min_fragments > 0, traverse_ldes_feed is called with max_fragments=min_fragments."""
        graph = ldes_graph_with_view()
        traversed = {self.URL}
        captured_kwargs = {}

        def fake_traverse(root_url, root_graph, timeout=30, max_fragments=None,
                          fragment_shapes_graph=None):
            captured_kwargs["max_fragments"] = max_fragments
            return root_graph, traversed, [], {}

        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed", side_effect=fake_traverse):
            run_ldes_validation(self.URL, min_fragments=3)

        assert captured_kwargs["max_fragments"] == 3

    def test_traverse_called_with_no_max_when_only_min_members_set(self):
        """When only min_members > 0 (no min_fragments), max_fragments is None."""
        graph = ldes_graph_with_view()
        traversed = {self.URL}
        captured_kwargs = {}

        def fake_traverse(root_url, root_graph, timeout=30, max_fragments=None,
                          fragment_shapes_graph=None):
            captured_kwargs["max_fragments"] = max_fragments
            return root_graph, traversed, [], {}

        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed", side_effect=fake_traverse):
            run_ldes_validation(self.URL, min_members=5)

        assert captured_kwargs["max_fragments"] is None


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

    def test_fragment_shapes_url_property_when_set(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results,
            suite_properties={
                "fragment_shapes_url": "https://example.org/frag-shapes.ttl",
            },
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert props.get("fragment_shapes_url") == "https://example.org/frag-shapes.ttl"

    def test_fragment_shapes_url_property_not_added_when_empty(self):
        results = [skipped_test("ldes_validation", "no config")]
        suites = self._write_and_parse(
            results,
            suite_properties={"fragment_shapes_url": ""},
        )
        props = {p.name: p.value for p in suites[0].properties()}
        assert "fragment_shapes_url" not in props


# ---------------------------------------------------------------------------
# _validate_fragment_graph
# ---------------------------------------------------------------------------


class TestValidateFragmentGraph:
    def test_returns_true_on_conformance(self):
        data = ldes_graph_with_view()
        shapes = make_graph()
        with patch("ldes_validation.shacl_validate", return_value=(True, None, "")):
            conforms, text = _validate_fragment_graph(data, shapes, "http://x")
        assert conforms is True
        assert text == ""

    def test_returns_false_on_violation(self):
        data = ldes_graph_with_view()
        shapes = make_graph()
        report = "Constraint violation on node X"
        with patch("ldes_validation.shacl_validate", return_value=(False, None, report)):
            conforms, text = _validate_fragment_graph(data, shapes, "http://x")
        assert conforms is False
        assert text == report

    def test_returns_none_on_exception(self):
        data = ldes_graph_with_view()
        shapes = make_graph()
        with patch("ldes_validation.shacl_validate", side_effect=Exception("boom")):
            conforms, text = _validate_fragment_graph(data, shapes, "http://x")
        assert conforms is None
        assert "boom" in text


# ---------------------------------------------------------------------------
# traverse_ldes_feed – fragment SHACL validation
# ---------------------------------------------------------------------------


class TestTraverseLdesFeedFragmentValidation:
    """Tests that traverse_ldes_feed validates each fragment when shapes are given."""

    ROOT_URL = "https://example.org/stream"
    VIEW_URL = "https://example.org/stream/view"
    CHILD_URL = "https://example.org/stream/page2"

    def test_fragment_validation_called_for_root_when_shapes_provided(self):
        """Root fragment is validated against shapes even with no child pages."""
        root_graph = make_graph(
            [(URIRef(self.ROOT_URL), RDF.type, LDES.EventStream)]
        )
        shapes = make_graph()

        with patch("ldes_validation.fetch_rdf_graph", side_effect=lambda u, t: (None, "err")), \
             patch("ldes_validation._validate_fragment_graph",
                   return_value=(True, "")) as mock_val:
            merged, traversed, errors, frag_val = traverse_ldes_feed(
                self.ROOT_URL, root_graph, fragment_shapes_graph=shapes,
            )

        # Root is always validated
        mock_val.assert_called_once_with(root_graph, shapes, self.ROOT_URL)
        assert self.ROOT_URL in frag_val
        assert frag_val[self.ROOT_URL] == (True, "")

    def test_fragment_validation_called_for_each_fetched_child(self):
        """Each successfully fetched child fragment is validated."""
        root_graph = ldes_graph_with_view()
        view_graph = make_graph(
            [(URIRef(self.VIEW_URL), TREE.node, URIRef(self.CHILD_URL))]
        )
        child_graph = make_graph(
            [(URIRef(self.CHILD_URL), RDF.type, TREE.Node)]
        )
        shapes = make_graph()

        def fetch_side_effect(url, timeout=30):
            if url == self.VIEW_URL:
                return view_graph, None
            if url == self.CHILD_URL:
                return child_graph, None
            return None, f"unexpected: {url}"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect), \
             patch("ldes_validation._validate_fragment_graph",
                   return_value=(True, "")) as mock_val:
            merged, traversed, errors, frag_val = traverse_ldes_feed(
                self.ROOT_URL, root_graph, fragment_shapes_graph=shapes,
            )

        # 3 calls: root + view + child
        assert mock_val.call_count == 3
        assert set(frag_val.keys()) == traversed

    def test_fragment_validation_not_called_when_no_shapes(self):
        """When fragment_shapes_graph is None, no validation occurs."""
        root_graph = ldes_graph_with_view()
        view_graph = make_graph()

        def fetch_side_effect(url, timeout=30):
            if url == self.VIEW_URL:
                return view_graph, None
            return None, f"unexpected: {url}"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_side_effect), \
             patch("ldes_validation._validate_fragment_graph") as mock_val:
            merged, traversed, errors, frag_val = traverse_ldes_feed(
                self.ROOT_URL, root_graph,
            )

        mock_val.assert_not_called()
        assert frag_val == {}

    def test_failed_fetches_are_not_validated(self):
        """Fragments that fail to fetch are not validated."""
        root_graph = ldes_graph_with_view()
        shapes = make_graph()

        def fetch_fail(url, timeout=30):
            return None, "fail"

        with patch("ldes_validation.fetch_rdf_graph", side_effect=fetch_fail), \
             patch("ldes_validation._validate_fragment_graph",
                   return_value=(True, "")) as mock_val:
            merged, traversed, errors, frag_val = traverse_ldes_feed(
                self.ROOT_URL, root_graph, fragment_shapes_graph=shapes,
            )

        # Only root was validated (view fetch failed)
        assert mock_val.call_count == 1
        assert frag_val == {self.ROOT_URL: (True, "")}


# ---------------------------------------------------------------------------
# run_ldes_validation – fragment SHACL test (Test 8)
# ---------------------------------------------------------------------------


class TestRunLdesValidationFragmentShacl:
    URL = "https://example.org/stream"

    def test_fragment_shacl_not_checked_when_none(self):
        """No ldes_fragment_shacl result when fragment_shapes_graph is None."""
        graph = ldes_graph_with_view()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(self.URL)
        assert not any("ldes_fragment_shacl" in r["case_name"] for r in results)

    def test_fragment_shacl_skipped_on_harvest_failure(self):
        """ldes_fragment_shacl is skipped when RDF harvest fails."""
        frag_shapes = make_graph()
        with patch(
            "ldes_validation.fetch_rdf_graph", return_value=(None, "timeout")
        ):
            results = run_ldes_validation(
                self.URL, fragment_shapes_graph=frag_shapes,
            )
        frag_result = next(
            (r for r in results if "ldes_fragment_shacl" in r["case_name"]), None,
        )
        assert frag_result is not None
        assert frag_result["skipped"] is True

    def test_fragment_shacl_skipped_on_no_event_stream(self):
        """ldes_fragment_shacl is skipped when no EventStream is found."""
        graph = plain_rdf_graph()
        frag_shapes = make_graph()
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)):
            results = run_ldes_validation(
                self.URL, fragment_shapes_graph=frag_shapes,
            )
        frag_result = next(
            (r for r in results if "ldes_fragment_shacl" in r["case_name"]), None,
        )
        assert frag_result is not None
        assert frag_result["skipped"] is True

    def test_fragment_shacl_passes_when_all_conform(self):
        """All fragments conform → ldes_fragment_shacl passes."""
        graph = ldes_graph_with_view()
        frag_shapes = make_graph()
        traversed = {self.URL}
        frag_validation = {self.URL: (True, "")}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], frag_validation)):
            results = run_ldes_validation(
                self.URL, fragment_shapes_graph=frag_shapes,
            )
        frag_result = next(
            r for r in results if "ldes_fragment_shacl" in r["case_name"]
        )
        assert frag_result["failure_message"] is None
        assert frag_result["error"] is None

    def test_fragment_shacl_fails_when_some_non_conforming(self):
        """Some fragments don't conform → ldes_fragment_shacl fails."""
        graph = ldes_graph_with_view()
        frag_shapes = make_graph()
        traversed = {self.URL, "https://example.org/stream/view"}
        frag_validation = {
            self.URL: (True, ""),
            "https://example.org/stream/view": (False, "Missing tree:Node type"),
        }
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], frag_validation)):
            results = run_ldes_validation(
                self.URL, fragment_shapes_graph=frag_shapes,
            )
        frag_result = next(
            r for r in results if "ldes_fragment_shacl" in r["case_name"]
        )
        assert frag_result["failure_message"] is not None
        assert "1 of 2" in frag_result["failure_message"]
        assert "do not conform" in frag_result["failure_message"]
        assert "stream/view" in frag_result["failure_text"]

    def test_fragment_shacl_error_on_shacl_engine_error(self):
        """SHACL engine error → ldes_fragment_shacl reports error."""
        graph = ldes_graph_with_view()
        frag_shapes = make_graph()
        traversed = {self.URL}
        frag_validation = {self.URL: (None, "pyshacl engine error")}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], frag_validation)):
            results = run_ldes_validation(
                self.URL, fragment_shapes_graph=frag_shapes,
            )
        frag_result = next(
            r for r in results if "ldes_fragment_shacl" in r["case_name"]
        )
        assert frag_result["error"] is not None
        assert "pyshacl engine error" in frag_result["error"]
        assert frag_result["failure_message"] is None  # no failure, only error


# ---------------------------------------------------------------------------
# extract_timestamp_path / extract_version_of_path
# ---------------------------------------------------------------------------


class TestExtractTimestampPath:
    def test_returns_empty_when_no_event_stream(self):
        """No ldes:EventStream means no timestampPath can be found."""
        g = plain_rdf_graph()
        assert extract_timestamp_path(g) == []

    def test_returns_empty_when_no_timestamp_path_declared(self):
        """EventStream without ldes:timestampPath returns empty list."""
        g = ldes_graph_with_view()
        assert extract_timestamp_path(g) == []

    def test_returns_declared_timestamp_path(self):
        """ldes:timestampPath is returned when declared on the EventStream."""
        stream = URIRef("https://example.org/stream")
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, LDES.timestampPath, DCT.modified))
        result = extract_timestamp_path(g)
        assert result == [DCT.modified]

    def test_returns_multiple_paths_from_multiple_streams(self):
        """Multiple EventStreams with different timestampPaths returns all of them."""
        stream1 = URIRef("https://example.org/stream1")
        stream2 = URIRef("https://example.org/stream2")
        g = Graph()
        g.add((stream1, RDF.type, LDES.EventStream))
        g.add((stream1, LDES.timestampPath, DCT.modified))
        g.add((stream2, RDF.type, LDES.EventStream))
        g.add((stream2, LDES.timestampPath, DCT.created))
        result = extract_timestamp_path(g)
        assert DCT.modified in result
        assert DCT.created in result
        assert len(result) == 2

    def test_deduplicates_identical_paths(self):
        """The same predicate declared on two streams appears only once."""
        stream1 = URIRef("https://example.org/stream1")
        stream2 = URIRef("https://example.org/stream2")
        g = Graph()
        g.add((stream1, RDF.type, LDES.EventStream))
        g.add((stream1, LDES.timestampPath, DCT.modified))
        g.add((stream2, RDF.type, LDES.EventStream))
        g.add((stream2, LDES.timestampPath, DCT.modified))
        result = extract_timestamp_path(g)
        assert result.count(DCT.modified) == 1


class TestExtractVersionOfPath:
    def test_returns_empty_when_no_event_stream(self):
        """No ldes:EventStream means no versionOfPath can be found."""
        g = plain_rdf_graph()
        assert extract_version_of_path(g) == []

    def test_returns_empty_when_no_version_of_path_declared(self):
        """EventStream without ldes:versionOfPath returns empty list."""
        g = ldes_graph_with_view()
        assert extract_version_of_path(g) == []

    def test_returns_declared_version_of_path(self):
        """ldes:versionOfPath is returned when declared on the EventStream."""
        stream = URIRef("https://example.org/stream")
        version_of = URIRef("http://purl.org/dc/terms/isVersionOf")
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, LDES.versionOfPath, version_of))
        result = extract_version_of_path(g)
        assert result == [version_of]

    def test_deduplicates_identical_paths(self):
        """The same predicate declared on two streams appears only once."""
        stream1 = URIRef("https://example.org/stream1")
        stream2 = URIRef("https://example.org/stream2")
        version_of = URIRef("http://purl.org/dc/terms/isVersionOf")
        g = Graph()
        g.add((stream1, RDF.type, LDES.EventStream))
        g.add((stream1, LDES.versionOfPath, version_of))
        g.add((stream2, RDF.type, LDES.EventStream))
        g.add((stream2, LDES.versionOfPath, version_of))
        result = extract_version_of_path(g)
        assert result.count(version_of) == 1


# ---------------------------------------------------------------------------
# find_youngest_member_timestamp
# ---------------------------------------------------------------------------


class TestFindYoungestMemberTimestamp:
    def _stream_with_member(self, member_uri="https://example.org/member/1"):
        stream = URIRef("https://example.org/stream")
        member = URIRef(member_uri)
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, TREE.member, member))
        return g, stream, member

    def test_returns_none_when_no_members(self):
        g = ldes_graph_with_view()
        assert find_youngest_member_timestamp(g) is None

    def test_returns_none_when_no_matching_timestamp(self):
        """Member has no known timestamp predicate → None."""
        g, _, member = self._stream_with_member()
        assert find_youngest_member_timestamp(g) is None

    def test_returns_timestamp_via_fallback_predicate(self):
        """Without ldes:timestampPath the fallback predicates are used."""
        g, _, member = self._stream_with_member()
        ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        g.add((member, DCT.modified, Literal(ts, datatype=XSD.dateTime)))
        result = find_youngest_member_timestamp(g)
        assert result is not None
        assert result == ts

    def test_uses_ldes_timestamp_path_when_declared(self):
        """When ldes:timestampPath is set, that predicate is used for timestamps."""
        stream = URIRef("https://example.org/stream")
        member = URIRef("https://example.org/member/1")
        custom_pred = URIRef("https://example.org/ns/eventTime")
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, LDES.timestampPath, custom_pred))
        g.add((stream, TREE.member, member))
        ts = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        g.add((member, custom_pred, Literal(ts, datatype=XSD.dateTime)))
        result = find_youngest_member_timestamp(g)
        assert result == ts

    def test_ignores_fallback_predicates_when_timestamp_path_declared(self):
        """When ldes:timestampPath is declared, fallback predicates are NOT checked."""
        stream = URIRef("https://example.org/stream")
        member = URIRef("https://example.org/member/1")
        custom_pred = URIRef("https://example.org/ns/eventTime")
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, LDES.timestampPath, custom_pred))
        g.add((stream, TREE.member, member))
        # Only DCT.modified is set (not custom_pred)
        fallback_ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
        g.add((member, DCT.modified, Literal(fallback_ts, datatype=XSD.dateTime)))
        # Because ldes:timestampPath points to custom_pred, DCT.modified is ignored
        result = find_youngest_member_timestamp(g)
        assert result is None

    def test_returns_youngest_across_multiple_members(self):
        """The most recent timestamp across multiple members is returned."""
        stream = URIRef("https://example.org/stream")
        member1 = URIRef("https://example.org/member/1")
        member2 = URIRef("https://example.org/member/2")
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, TREE.member, member1))
        g.add((stream, TREE.member, member2))
        old_ts = datetime(2023, 1, 1, tzinfo=timezone.utc)
        new_ts = datetime(2024, 6, 15, tzinfo=timezone.utc)
        g.add((member1, DCT.modified, Literal(old_ts, datatype=XSD.dateTime)))
        g.add((member2, DCT.modified, Literal(new_ts, datatype=XSD.dateTime)))
        result = find_youngest_member_timestamp(g)
        assert result == new_ts

    def test_timestamp_path_from_stream_used_on_all_members(self):
        """ldes:timestampPath declared on the stream applies to all its members."""
        stream = URIRef("https://example.org/stream")
        member1 = URIRef("https://example.org/member/1")
        member2 = URIRef("https://example.org/member/2")
        custom_pred = URIRef("https://example.org/ns/eventTime")
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, LDES.timestampPath, custom_pred))
        g.add((stream, TREE.member, member1))
        g.add((stream, TREE.member, member2))
        ts1 = datetime(2024, 3, 10, tzinfo=timezone.utc)
        ts2 = datetime(2024, 7, 20, tzinfo=timezone.utc)
        g.add((member1, custom_pred, Literal(ts1, datatype=XSD.dateTime)))
        g.add((member2, custom_pred, Literal(ts2, datatype=XSD.dateTime)))
        result = find_youngest_member_timestamp(g)
        assert result == ts2


# ---------------------------------------------------------------------------
# run_ldes_validation – max_age_youngest_member uses ldes:timestampPath
# ---------------------------------------------------------------------------


class TestMaxAgeYoungestMemberWithTimestampPath:
    """Verify that max_age_youngest_member respects ldes:timestampPath."""

    URL = "https://example.org/stream"

    def _graph_with_timestamp_path(self, custom_pred, member_ts):
        """Build an LDES graph with ldes:timestampPath and a member timestamp."""
        stream = URIRef("https://example.org/stream")
        view = URIRef("https://example.org/stream/view")
        member = URIRef("https://example.org/member/1")
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, TREE.view, view))
        g.add((stream, LDES.timestampPath, custom_pred))
        g.add((stream, TREE.member, member))
        g.add((member, custom_pred, Literal(member_ts, datatype=XSD.dateTime)))
        return g

    def test_passes_when_custom_timestamp_path_is_recent(self):
        """max_age check passes when the custom predicate carries a recent timestamp."""
        custom_pred = URIRef("https://example.org/ns/eventTime")
        recent_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        graph = self._graph_with_timestamp_path(custom_pred, recent_ts)
        traversed = {self.URL}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], {})):
            results = run_ldes_validation(
                self.URL, max_age_youngest_member=24,
            )
        age_result = next(
            r for r in results if "ldes_max_age_youngest_member" in r["case_name"]
        )
        assert age_result["failure_message"] is None
        assert age_result["error"] is None

    def test_fails_when_custom_timestamp_path_is_old(self):
        """max_age check fails when only the custom predicate has an old timestamp."""
        custom_pred = URIRef("https://example.org/ns/eventTime")
        old_ts = datetime.now(timezone.utc) - timedelta(hours=100)
        graph = self._graph_with_timestamp_path(custom_pred, old_ts)
        traversed = {self.URL}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(graph, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(graph, traversed, [], {})):
            results = run_ldes_validation(
                self.URL, max_age_youngest_member=24,
            )
        age_result = next(
            r for r in results if "ldes_max_age_youngest_member" in r["case_name"]
        )
        assert age_result["failure_message"] is not None
        assert "too old" in age_result["failure_message"].lower() or "exceeds" in age_result["failure_message"].lower()

    def test_failure_text_lists_custom_predicate(self):
        """When no timestamp is found, failure_text names the custom predicate."""
        custom_pred = URIRef("https://example.org/ns/eventTime")
        stream = URIRef("https://example.org/stream")
        view = URIRef("https://example.org/stream/view")
        member = URIRef("https://example.org/member/1")
        # Member has DCT.modified but stream declares a custom timestampPath
        g = Graph()
        g.add((stream, RDF.type, LDES.EventStream))
        g.add((stream, TREE.view, view))
        g.add((stream, LDES.timestampPath, custom_pred))
        g.add((stream, TREE.member, member))
        recent_ts = datetime.now(timezone.utc) - timedelta(hours=1)
        g.add((member, DCT.modified, Literal(recent_ts, datatype=XSD.dateTime)))
        traversed = {self.URL}
        with patch("ldes_validation.fetch_rdf_graph", return_value=(g, None)), \
             patch("ldes_validation.traverse_ldes_feed",
                   return_value=(g, traversed, [], {})):
            results = run_ldes_validation(
                self.URL, max_age_youngest_member=24,
            )
        age_result = next(
            r for r in results if "ldes_max_age_youngest_member" in r["case_name"]
        )
        # DCT.modified value is NOT found via custom_pred → no timestamp
        assert age_result["failure_message"] == "No timestamp found on any tree:member"
        assert str(custom_pred) in age_result["failure_text"]

