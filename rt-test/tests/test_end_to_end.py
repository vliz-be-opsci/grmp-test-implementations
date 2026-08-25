"""
End-to-end integration tests for RT test suite execution and JUnit report generation.
"""

import os
import tempfile
import httpx
import respx
from junitparser import JUnitXml
from src.config.loader import load_config_from_yaml
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
