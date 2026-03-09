#!/usr/bin/env python3
"""
Unit tests for semantic_harvest.py

Run with (from semantic-harvest/ root):
    pip install pytest junitparser pysema rdflib
    pytest tests/test_semantic_harvest.py -v
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from rdflib import Graph, URIRef, Literal

from semantic_harvest import (
    parse_config,
    run_harvest_test,
    skipped_test,
    create_junit_report,
    RDF_FORMATS,
)


# ---------------------------------------------------------------------------
# parse_config
# ---------------------------------------------------------------------------

class TestParseConfig:
    def test_default_empty_urls(self):
        with patch.dict(os.environ, {"TEST_URLS": "[]"}, clear=False):
            config = parse_config()
        assert config["urls"] == []

    def test_single_url_string(self):
        with patch.dict(os.environ, {"TEST_URLS": "'https://example.com'"}, clear=False):
            config = parse_config()
        assert config["urls"] == ["https://example.com"]

    def test_list_of_urls(self):
        with patch.dict(
            os.environ,
            {"TEST_URLS": "['https://example.com', 'https://schema.org/']"},
            clear=False,
        ):
            config = parse_config()
        assert config["urls"] == ["https://example.com", "https://schema.org/"]

    def test_invalid_urls_env_falls_back_to_empty(self):
        with patch.dict(os.environ, {"TEST_URLS": "not-valid-python"}, clear=False):
            config = parse_config()
        assert config["urls"] == []

    def test_default_formats(self):
        with patch.dict(os.environ, {}, clear=False):
            config = parse_config()
        assert config["formats"] == RDF_FORMATS

    def test_custom_formats(self):
        with patch.dict(
            os.environ,
            {"TEST_RDF-FORMATS": "text/turtle,application/ld+json"},
            clear=False,
        ):
            config = parse_config()
        assert config["formats"] == ["text/turtle", "application/ld+json"]

    def test_providence_default(self):
        env = {k: v for k, v in os.environ.items() if k != "SPECIAL_SOURCE_FILE"}
        with patch.dict(os.environ, env, clear=True):
            config = parse_config()
        assert config["providence"] == "unknown"

    def test_providence_custom(self):
        with patch.dict(os.environ, {"SPECIAL_SOURCE_FILE": "myfile.yaml"}, clear=False):
            config = parse_config()
        assert config["providence"] == "myfile.yaml"


# ---------------------------------------------------------------------------
# skipped_test
# ---------------------------------------------------------------------------

class TestSkippedTest:
    def test_returns_skipped_result(self):
        result = skipped_test("my_test", "No URLs configured")
        assert result["skipped"] is True
        assert result["skipped_message"] == "No URLs configured"
        assert result["case_name"] == "my_test"
        assert result["failure_message"] is None
        assert result["error"] is None


# ---------------------------------------------------------------------------
# run_harvest_test
# ---------------------------------------------------------------------------

class TestRunHarvestTest:
    def _make_graph(self, triples=1):
        g = Graph()
        if triples > 0:
            g.add((URIRef("http://example.com/s"), URIRef("http://example.com/p"), Literal("o")))
        return g

    def test_success_non_empty_graph(self):
        graph = self._make_graph(1)
        with patch("semantic_harvest.get_graph_for_format", return_value=graph):
            result = run_harvest_test("https://example.com", RDF_FORMATS)
        assert result["failure_message"] is None
        assert result["error"] is None
        assert result["skipped"] is False
        assert "triple_count" in result["properties"]

    def test_failure_empty_graph(self):
        graph = self._make_graph(0)
        with patch("semantic_harvest.get_graph_for_format", return_value=graph):
            result = run_harvest_test("https://example.com", RDF_FORMATS)
        assert result["failure_message"] == "Empty RDF graph harvested"
        assert result["error"] is None

    def test_failure_none_graph(self):
        with patch("semantic_harvest.get_graph_for_format", return_value=None):
            result = run_harvest_test("https://example.com", RDF_FORMATS)
        assert result["failure_message"] == "No RDF graph could be harvested"
        assert result["error"] is None

    def test_exception_becomes_error(self):
        with patch(
            "semantic_harvest.get_graph_for_format",
            side_effect=Exception("connection refused"),
        ):
            result = run_harvest_test("https://example.com", RDF_FORMATS)
        assert result["error"] is not None
        assert "connection refused" in result["error"]
        assert result["failure_message"] is None

    def test_case_name_contains_url(self):
        graph = self._make_graph(1)
        url = "https://schema.org/"
        with patch("semantic_harvest.get_graph_for_format", return_value=graph):
            result = run_harvest_test(url, RDF_FORMATS)
        assert url in result["case_name"]


# ---------------------------------------------------------------------------
# create_junit_report
# ---------------------------------------------------------------------------

class TestCreateJunitReport:
    def test_creates_xml_file(self, tmp_path):
        output_file = str(tmp_path / "output.xml")
        graph = Graph()
        graph.add((URIRef("http://s"), URIRef("http://p"), Literal("o")))
        with patch("semantic_harvest.get_graph_for_format", return_value=graph):
            results = [run_harvest_test("https://example.com", RDF_FORMATS)]
        create_junit_report(
            "semantic-harvest",
            results,
            output_file,
            special_key_append_properties={"urls"},
            providence="test",
        )
        assert os.path.exists(output_file)
        with open(output_file) as f:
            content = f.read()
        assert "semantic-harvest" in content
        assert "semantic_harvest" in content

    def test_skipped_result_in_report(self, tmp_path):
        output_file = str(tmp_path / "output.xml")
        results = [skipped_test("semantic_harvest", "No URLs configured")]
        create_junit_report(
            "semantic-harvest",
            results,
            output_file,
            special_key_append_properties={"urls"},
            providence="test",
        )
        assert os.path.exists(output_file)
        with open(output_file) as f:
            content = f.read()
        assert "skipped" in content.lower() or "No URLs configured" in content

    def test_failure_result_in_report(self, tmp_path):
        output_file = str(tmp_path / "output.xml")
        with patch("semantic_harvest.get_graph_for_format", return_value=None):
            results = [run_harvest_test("https://example.com", RDF_FORMATS)]
        create_junit_report(
            "semantic-harvest",
            results,
            output_file,
            special_key_append_properties={"urls"},
            providence="test",
        )
        assert os.path.exists(output_file)
        with open(output_file) as f:
            content = f.read()
        assert "failure" in content.lower()
