"""
End-to-end integration tests for RT test suite execution and JUnit report generation.
"""

import os
import tempfile
import pytest
import httpx
import respx
from junitparser import JUnitXml
from src.config.loader import load_config_from_file, load_config_from_yaml
from src.evaluator.runner import SuiteRunner
from src.reporter.junit import generate_junit_xml


@respx.mock
def test_end_to_end_suite_run_and_junit_xml():
    # Mock dataset 1
    respx.get("https://example.org/dataset/1").respond(
        status_code=200,
        headers={
            "Link": '<https://example.org/profiles/dcat-ap>; rel="profile", </meta.jsonld>; rel="describedby"; type="application/ld+json", <https://doi.org/10.1234/5678>; rel="cite-as"',
            "Content-Type": "text/html",
        },
        html="<html><body><h1>Dataset 1</h1></body></html>",
    )

    yaml_config = """
    version: "1.0"
    name: "eosc-rt-testsuite"
    tests:
      - name: "Dataset Conformance Check"
        targets:
          urls:
            - "https://example.org/dataset/1"
        expect:
          relations:
            - rel: "profile"
              target: "https://example.org/profiles/dcat-ap"
              exists: true
            - rel: "describedby"
              type: "application/ld+json"
              min_count: 1
            - rel: "cite-as"
              target_pattern: "^https://doi\\\\.org/10\\\\..*"
              exists: true
    """

    suite_config = load_config_from_yaml(yaml_config)
    runner = SuiteRunner()

    with httpx.Client() as client:
        results = runner.run_suite(suite_config, client=client)

    assert len(results) == 3
    assert all(r.passed for r in results)

    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = os.path.join(tmpdir, "report.xml")
        generate_junit_xml(
            suite_name=suite_config.name,
            results=results,
            output_file=report_file,
            provenance="test_run",
        )

        assert os.path.exists(report_file)
        xml = JUnitXml.fromfile(report_file)
        testsuites = list(xml)
        assert len(testsuites) == 1
        suite = testsuites[0]
        assert suite.name == "eosc-rt-testsuite"
        cases = list(suite)
        assert len(cases) == 3
        for c in cases:
            assert len(c.result) == 0  # No failure / error


def test_example_config_yaml_file_loading():
    """Verify example_config.yaml is valid, parsable, and defines localhost:8080 targets."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "example_config.yaml")
    assert os.path.isfile(config_path), f"Config file not found at {config_path}"

    suite_config = load_config_from_file(config_path)
    assert len(suite_config.tests) >= 5
    assert any("localhost:8080" in url for test in suite_config.tests for url in test.targets.urls)


def test_example_config_against_localhost_8080_if_live():
    """If localhost:8080 is reachable (e.g. running reference container), verify all assertions pass."""
    try:
        r = httpx.get("http://localhost:8080/sitemap.xml", timeout=2.0)
        if r.status_code != 200:
            pytest.skip("localhost:8080 container is not returning 200 OK")
    except Exception:
        pytest.skip("localhost:8080 container is not reachable")

    config_path = os.path.join(os.path.dirname(__file__), "..", "example_config.yaml")
    suite_config = load_config_from_file(config_path)
    runner = SuiteRunner()

    with httpx.Client(timeout=10.0) as client:
        results = runner.run_suite(suite_config, client=client)

    assert len(results) > 0
    failures = [r for r in results if not r.passed]
    assert len(failures) == 0, f"{len(failures)} assertion(s) failed: {[f.failure_message for f in failures]}"
