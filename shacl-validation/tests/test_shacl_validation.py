#!/usr/bin/env python3
"""
Unit tests for shacl_validation.py

Run with (from shacl-validation/ root):
    pip install pytest junitparser pyshacl rdflib py-sema
    pytest tests/test_shacl_validation.py -v
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from rdflib import Graph

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shacl_validation import (
    create_junit_report,
    harvest_graph,
    parse_config,
    run_shacl_test,
    skipped_test,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_graph(triples=0):
    """Return a minimal rdflib.Graph with the given number of fake triples."""
    g = Graph()
    for i in range(triples):
        from rdflib import URIRef
        g.add((URIRef(f"urn:s{i}"), URIRef(f"urn:p{i}"), URIRef(f"urn:o{i}")))
    return g


# ---------------------------------------------------------------------------
# parse_config
# ---------------------------------------------------------------------------

class TestParseConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("TEST_DATA_URLS", raising=False)
        monkeypatch.delenv("TEST_SHAPES_URL", raising=False)
        monkeypatch.delenv("TEST_TIMEOUT", raising=False)
        monkeypatch.delenv("SPECIAL_SOURCE_FILE", raising=False)
        config = parse_config()
        assert config["data_urls"] == []
        assert config["shapes_url"] == ""
        assert config["timeout"] == 30
        assert config["providence"] == "unknown"

    def test_single_url_string(self, monkeypatch):
        # A quoted string is a valid Python literal so ast.literal_eval returns a str
        monkeypatch.setenv("TEST_DATA_URLS", "'https://example.org/data'")
        monkeypatch.setenv("TEST_SHAPES_URL", "https://example.org/shapes.ttl")
        config = parse_config()
        assert config["data_urls"] == ["https://example.org/data"]
        assert config["shapes_url"] == "https://example.org/shapes.ttl"

    def test_list_of_urls(self, monkeypatch):
        monkeypatch.setenv(
            "TEST_DATA_URLS",
            "['https://example.org/data1', 'https://example.org/data2']",
        )
        config = parse_config()
        assert config["data_urls"] == [
            "https://example.org/data1",
            "https://example.org/data2",
        ]

    def test_invalid_urls_env(self, monkeypatch):
        monkeypatch.setenv("TEST_DATA_URLS", "not valid python")
        config = parse_config()
        assert config["data_urls"] == []

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

    def test_providence(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "my_source.yaml")
        config = parse_config()
        assert config["providence"] == "my_source.yaml"


# ---------------------------------------------------------------------------
# harvest_graph
# ---------------------------------------------------------------------------

class TestHarvestGraph:
    def test_success(self):
        mock_graph = make_graph(3)
        with patch("shacl_validation.url_to_graph", return_value=mock_graph):
            graph, error = harvest_graph("https://example.org/data")
        assert error is None
        assert graph is mock_graph

    def test_url_to_graph_raises(self):
        with patch("shacl_validation.url_to_graph", side_effect=Exception("network error")):
            graph, error = harvest_graph("https://example.org/bad")
        assert graph is None
        assert "network error" in error


# ---------------------------------------------------------------------------
# run_shacl_test
# ---------------------------------------------------------------------------

class TestRunShaclTest:
    def test_conforms(self):
        data_graph = make_graph(2)
        shapes_graph = make_graph(1)
        with patch("shacl_validation.url_to_graph", return_value=data_graph), \
             patch("shacl_validation.validate", return_value=(True, None, "")):
            result = run_shacl_test("https://example.org/data", shapes_graph)
        assert result["failure_message"] is None
        assert result["error"] is None
        assert result["skipped"] is False
        assert "shacl_validation [https://example.org/data]" == result["case_name"]

    def test_does_not_conform(self):
        data_graph = make_graph(2)
        shapes_graph = make_graph(1)
        report_text = "Constraint violation found"
        with patch("shacl_validation.url_to_graph", return_value=data_graph), \
             patch("shacl_validation.validate", return_value=(False, None, report_text)):
            result = run_shacl_test("https://example.org/data", shapes_graph)
        assert result["failure_message"] == "SHACL validation failed"
        assert result["failure_text"] == report_text
        assert result["error"] is None

    def test_harvest_error(self):
        shapes_graph = make_graph(1)
        with patch("shacl_validation.url_to_graph", side_effect=Exception("timeout")):
            result = run_shacl_test("https://example.org/bad", shapes_graph)
        assert result["error"] is not None
        assert "timeout" in result["error"]
        assert result["failure_message"] is None

    def test_validate_raises(self):
        data_graph = make_graph(2)
        shapes_graph = make_graph(1)
        with patch("shacl_validation.url_to_graph", return_value=data_graph), \
             patch("shacl_validation.validate", side_effect=Exception("pyshacl error")):
            result = run_shacl_test("https://example.org/data", shapes_graph)
        assert result["error"] is not None
        assert "pyshacl error" in result["error"]

    def test_data_url_in_properties(self):
        data_graph = make_graph(0)
        shapes_graph = make_graph(0)
        with patch("shacl_validation.url_to_graph", return_value=data_graph), \
             patch("shacl_validation.validate", return_value=(True, None, "")):
            result = run_shacl_test("https://example.org/mydata", shapes_graph)
        assert result["properties"]["data_urls"] == "https://example.org/mydata"


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
    def _write_and_parse(self, results, shapes_url="", providence="test-prov"):
        from junitparser import JUnitXml
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f:
            path = f.name
        try:
            create_junit_report(
                "shacl-validation",
                results,
                output_file=path,
                shapes_url=shapes_url,
                providence=providence,
            )
            xml = JUnitXml.fromfile(path)
            return list(xml)
        finally:
            os.unlink(path)

    def test_passing_test(self):
        results = [
            {
                "case_name": "shacl_validation [https://example.org/data]",
                "duration": 0.5,
                "error": None,
                "failure_message": None,
                "failure_text": None,
                "properties": {"data_urls": "https://example.org/data"},
                "skipped": False,
                "skipped_message": "",
                "stdout": "Validation passed",
                "stderr": "",
            }
        ]
        suites = self._write_and_parse(results)
        assert len(suites) == 1
        cases = list(suites[0])
        assert len(cases) == 1
        assert cases[0].result == [] or cases[0].result is None or all(r is None for r in cases[0].result)

    def test_failing_test(self):
        from junitparser import Failure
        results = [
            {
                "case_name": "shacl_validation [https://example.org/data]",
                "duration": 0.3,
                "error": None,
                "failure_message": "SHACL validation failed",
                "failure_text": "Constraint violation",
                "properties": {"data_urls": "https://example.org/data"},
                "skipped": False,
                "skipped_message": "",
                "stdout": "",
                "stderr": "SHACL validation failed",
            }
        ]
        suites = self._write_and_parse(results)
        cases = list(suites[0])
        assert len(cases) == 1
        assert any(isinstance(r, Failure) for r in cases[0].result)

    def test_skipped_test(self):
        from junitparser import Skipped
        results = [skipped_test("shacl_validation", "No config")]
        suites = self._write_and_parse(results)
        cases = list(suites[0])
        assert any(isinstance(r, Skipped) for r in cases[0].result)

    def test_error_test(self):
        from junitparser import Error
        results = [
            {
                "case_name": "shacl_validation [https://example.org/data]",
                "duration": 0.1,
                "error": "Could not harvest data graph: timeout",
                "failure_message": None,
                "failure_text": None,
                "properties": {"data_urls": "https://example.org/data"},
                "skipped": False,
                "skipped_message": "",
                "stdout": "",
                "stderr": "timeout",
            }
        ]
        suites = self._write_and_parse(results)
        cases = list(suites[0])
        assert any(isinstance(r, Error) for r in cases[0].result)

    def test_shapes_url_as_property(self):
        results = [skipped_test("shacl_validation", "no config")]
        suites = self._write_and_parse(
            results,
            shapes_url="https://example.org/shapes.ttl",
        )
        suite = suites[0]
        props = {p.name: p.value for p in suite.properties()}
        assert props.get("shapes_url") == "https://example.org/shapes.ttl"

    def test_data_urls_as_property(self):
        results = [
            {
                "case_name": "shacl_validation [https://example.org/data]",
                "duration": 0.1,
                "error": None,
                "failure_message": None,
                "failure_text": None,
                "properties": {"data_urls": "https://example.org/data"},
                "skipped": False,
                "skipped_message": "",
                "stdout": "",
                "stderr": "",
            }
        ]
        suites = self._write_and_parse(results)
        suite = suites[0]
        props = {p.name: p.value for p in suite.properties()}
        assert "data_urls" in props
        assert "https://example.org/data" in props["data_urls"]

    def test_providence_property(self):
        results = [skipped_test("shacl_validation", "no config")]
        suites = self._write_and_parse(results, providence="my_providence_file.yaml")
        suite = suites[0]
        props = {p.name: p.value for p in suite.properties()}
        assert props.get("providence") == "my_providence_file.yaml"
