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


def _build_testcase_system_out(res: AssertionResult) -> str:
    """Build a rich, structured diagnostic system-out for a JUnit XML testcase."""
    lines = []

    # 1. Status & Pattern / Suite Context
    status_label = "PASSED" if res.passed and not res.skipped else ("SKIPPED" if res.skipped else "FAILED")
    lines.append(f"Outcome: {status_label}")
    if res.pattern_id:
        p_name = f" ({res.pattern_name})" if res.pattern_name else ""
        lines.append(f"Pattern: [{res.pattern_id}]{p_name}")
    if res.suite_name:
        lines.append(f"Test Definition: {res.suite_name}")

    # 2. Target Harvest Info
    node = res.harvest_node
    if node:
        status_code = f"HTTP {node.status_code}" if node.status_code else "HTTP Error"
        ct = f" {node.content_type}" if node.content_type else ""
        dur = f" in {node.duration:.3f}s" if getattr(node, "duration", 0) > 0 else ""
        lines.append(f"Target URL: {node.uri} ({status_code}{ct}{dur})")

        dir_cnt = len(node.direct_links)
        exp_cnt = len(node.expanded_links)
        ls_cnt = len(node.referenced_linksets)
        link_str = f"{len(node.all_links)} total links ({dir_cnt} direct"
        if exp_cnt > 0 or ls_cnt > 0:
            link_str += f", {exp_cnt} expanded via {ls_cnt} linkset(s)"
        link_str += ")"
        lines.append(f"Discovered Links: {link_str}")
    elif res.target_url:
        lines.append(f"Target URL: {res.target_url}")

    # 3. Evaluated Expectation
    if res.expectation:
        lines.append(f"Evaluated Expectation: {res.expectation.description()}")

    # 4. Matched Links & Carrier Sources
    if res.matched_links:
        sources = []
        seen = set()
        for link in res.matched_links:
            src = getattr(link, "source", None)
            if src and src not in seen:
                seen.add(src)
                sources.append(src)
        source_badge = f" [source: {', '.join(sources)}]" if sources else ""
        lines.append(f"Matched Relations Count: {len(res.matched_links)}{source_badge}")
        lines.append("Matched:")
        for idx, ml in enumerate(res.matched_links, 1):
            lines.append(f"  [{idx}] {ml.display_repr()}")
    elif res.passed:
        lines.append("Matched: 0 relations (as expected)")
    else:
        lines.append("Matched Relations Count: 0")

    # 5. Generic stdout if expectation wasn't set (e.g. SPARQL / Harvest)
    if not res.expectation and res.stdout and res.stdout not in "\n".join(lines):
        lines.append(res.stdout)

    # 6. Failure / Error details
    if not res.passed:
        if res.failure_message:
            lines.append(f"Failure Reason: {res.failure_message}")
        if res.failure_text and res.failure_text != res.failure_message:
            lines.append(res.failure_text)
        if res.error:
            lines.append(f"Error: {res.error}")

    # 7. ASCII Diagram if present
    if res.diagram:
        lines.append("")
        lines.append(res.diagram)

    return "\n".join(lines)


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

            case.system_out = _build_testcase_system_out(res)
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
