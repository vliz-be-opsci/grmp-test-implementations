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
    try:
        return urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return ""


def generate_junit_xml(
    suite_name: str,
    results: List[AssertionResult],
    output_file: str,
    provenance: str = "unknown",
    create_issue: bool = False,
    extra_properties: Optional[Dict[str, str]] = None,
) -> None:
    """
    Generate and write a standard JUnit XML report file.

    If results contain multiple distinct suite_name values (corresponding to
    named test definitions in YAML), each test definition is written as its own
    TestSuite in the report.
    """
    grouped_results: Dict[str, List[AssertionResult]] = {}
    for res in results:
        s_name = res.suite_name or suite_name
        if s_name not in grouped_results:
            grouped_results[s_name] = []
        grouped_results[s_name].append(res)

    if not grouped_results:
        grouped_results[suite_name] = []

    now_iso = datetime.now(timezone.utc).isoformat()
    xml = JUnitXml()

    for group_name, group_cases in grouped_results.items():
        suite = TestSuite(group_name)
        suite.timestamp = now_iso
        total_time = 0.0

        urls_seen: List[str] = []
        hostnames_seen: List[str] = []

        for res in group_cases:
            case = TestCase(res.case_name, classname=group_name)
            case.time = res.duration
            total_time += res.duration

            if res.target_url:
                if res.target_url not in urls_seen:
                    urls_seen.append(res.target_url)
                h = _hostname(res.target_url)
                if h and h not in hostnames_seen:
                    hostnames_seen.append(h)

            if res.skipped:
                case.result = [Skipped(message=res.skipped_message or "Test skipped")]
            elif res.error is not None:
                err = Error(message="Unexpected error")
                err.text = str(res.error)
                case.result = [err]
            elif not res.passed:
                failure = Failure(message=res.failure_message or "Assertion failed")
                failure.text = res.failure_text or res.failure_message or "Assertion failed"
                case.result = [failure]

            if res.stdout:
                case.system_out = res.stdout
            if res.stderr:
                case.system_err = res.stderr

            suite.add_testcase(case)

        if urls_seen:
            suite.add_property("urls", ", ".join(urls_seen))
        if hostnames_seen:
            suite.add_property("hostnames", ", ".join(hostnames_seen))

        suite.add_property("provenance", provenance)
        suite.add_property("create-issue", str(create_issue).lower())

        if extra_properties:
            for k, v in extra_properties.items():
                if k not in ("urls", "hostnames", "provenance", "create-issue"):
                    suite.add_property(k, str(v))

        suite.time = total_time
        xml.add_testsuite(suite)

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    xml.write(output_file)
