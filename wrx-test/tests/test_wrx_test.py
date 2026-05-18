#!/usr/bin/env python3
"""
Unit tests for wrx_test.py
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from wrx_test import (
    parse_config,
    run_wrx_triples_test,
    run_tests_for_url,
    create_junit_report,
    skipped_test,
)


class TestParseConfig:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("TEST_URLS", raising=False)
        monkeypatch.delenv("TEST_MIN-TRIPLES", raising=False)
        monkeypatch.delenv("SPECIAL_SOURCE_FILE", raising=False)
        monkeypatch.delenv("SPECIAL_CREATE_ISSUE", raising=False)

        config = parse_config()
        assert config["urls"] == []
        assert config["min_triples"] == 1
        assert config["provenance"] == "unknown"
        assert config["create_issue"] is False

    def test_custom_values(self, monkeypatch):
        monkeypatch.setenv("TEST_URLS", "['https://example.org']")
        monkeypatch.setenv("TEST_MIN-TRIPLES", "5")
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "cfg.yaml")
        monkeypatch.setenv("SPECIAL_CREATE_ISSUE", "true")

        config = parse_config()
        assert config["urls"] == ["https://example.org"]
        assert config["min_triples"] == 5
        assert config["provenance"] == "cfg.yaml"
        assert config["create_issue"] is True

    def test_invalid_min_triples_falls_back(self, monkeypatch):
        monkeypatch.setenv("TEST_MIN-TRIPLES", "0")
        assert parse_config()["min_triples"] == 1


class TestRunWrxTriplesTest:
    def test_passes_when_minimum_met(self):
        with patch(
            "wrx_test._run_wrx_extractor",
            return_value={
                "ok": True,
                "format": "text/turtle",
                "content": "<http://ex/s> <http://ex/p> <http://ex/o> .",
                "source": "content-negotiation",
            },
        ):
            result = run_wrx_triples_test("https://example.org", min_triples=1)

        assert result["failure_message"] is None
        assert result["error"] is None
        assert result["properties"]["triples-found"] == "1"

    def test_fails_when_below_minimum(self):
        with patch(
            "wrx_test._run_wrx_extractor",
            return_value={
                "ok": True,
                "format": "text/turtle",
                "content": "<http://ex/s> <http://ex/p> <http://ex/o> .",
            },
        ):
            result = run_wrx_triples_test("https://example.org", min_triples=2)

        assert result["failure_message"] == "Insufficient triples found"
        assert result["error"] is None

    def test_fails_when_wrx_returns_no_rdf(self):
        with patch(
            "wrx_test._run_wrx_extractor",
            return_value={"ok": False, "reason": "No RDF extracted"},
        ):
            result = run_wrx_triples_test("https://example.org", min_triples=1)

        assert result["failure_message"] == "No RDF triples found by wrx"
        assert result["error"] is None

    def test_sets_error_when_subprocess_fails(self):
        with patch("wrx_test._run_wrx_extractor", side_effect=RuntimeError("boom")):
            result = run_wrx_triples_test("https://example.org", min_triples=1)

        assert result["error"] is not None
        assert "boom" in result["error"]


class TestRunTestsForUrl:
    def test_returns_single_result(self):
        with patch(
            "wrx_test.run_wrx_triples_test",
            return_value={"case_name": "wrx_triples [https://example.org]"},
        ):
            results = run_tests_for_url("https://example.org", {"min_triples": 3})

        assert len(results) == 1


class TestSkippedTest:
    def test_returns_skipped_result(self):
        result = skipped_test("wrx_triples", "No URL(s) configured")
        assert result["skipped"] is True
        assert result["skipped_message"] == "No URL(s) configured"


class TestCreateJunitReport:
    def test_writes_report(self, tmp_path):
        out = str(tmp_path / "report.xml")
        results = [{
            "case_name": "wrx_triples [https://example.org]",
            "duration": 0.1,
            "error": None,
            "failure_message": None,
            "failure_text": None,
            "properties": {"urls": "https://example.org", "hostnames": "example.org"},
            "skipped": False,
            "skipped_message": "",
            "stdout": "ok",
            "stderr": "",
        }]

        create_junit_report(
            "wrx-test",
            results,
            out,
            special_key_append_properties={"urls", "hostnames"},
            provenance="cfg.yaml",
            suite_properties={"min_triples": 1, "create_issue": True},
        )

        assert os.path.exists(out)
        content = open(out).read()
        assert 'name="min-triples" value="1"' in content
        assert 'name="create-issue" value="true"' in content
