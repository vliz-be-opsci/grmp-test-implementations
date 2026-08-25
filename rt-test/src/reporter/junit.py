"""
JUnit XML Report generator for RT test runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import urllib.parse
from typing import Dict, List, Optional

from junitparser import Error, Failure, JUnitXml, Skipped, TestCase, TestSuite

from evaluator.matcher import AssertionResult


def _hostname(url: str) -> str:
    return urllib.parse.urlparse(url).hostname or url


def generate_junit_xml(
    suite_name: str,
    results: List[AssertionResult],
    output_file: str,
    provenance: str = "unknown",
    create_issue: bool = False,
    extra_properties: Optional[Dict[str, str]] = None,
) -> None:
    """Generate and write a standard JUnit XML report file."""
    suite = TestSuite(suite_name)
    suite.timestamp = datetime.now(timezone.utc).isoformat()
    total_time = 0.0

    urls_seen = set()
    hostnames_seen = set()

    for res in results:
        case = TestCase(res.case_name, classname=suite_name)
        case.time = res.duration
        total_time += res.duration

        if res.target_url:
            urls_seen.add(res.target_url)
            hostnames_seen.add(_hostname(res.target_url))

        for k, v in res.properties.items():
            if k not in ("url", "urls", "hostnames"):
                suite.add_property(f"case.{res.case_name}.{k}", str(v))

        if not res.passed:
            failure = Failure(message=res.failure_message or "Assertion failed")
            failure.text = res.failure_text or res.failure_message or "Assertion failed"
            case.result = [failure]

        suite.add_testcase(case)

    if urls_seen:
        suite.add_property("urls", ", ".join(sorted(urls_seen)))
    if hostnames_seen:
        suite.add_property("hostnames", ", ".join(sorted(hostnames_seen)))

    suite.add_property("provenance", provenance)
    suite.add_property("create-issue", str(create_issue).lower())

    if extra_properties:
        for k, v in extra_properties.items():
            suite.add_property(k, str(v))

    suite.time = total_time

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)
