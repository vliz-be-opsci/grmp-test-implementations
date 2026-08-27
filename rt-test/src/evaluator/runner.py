"""
Test runner executing suites of RT tests and evaluating assertions.
"""

from __future__ import annotations

import fnmatch
import re
import time
from typing import List, Optional
import httpx

from config.models import TestCaseConfig, TestSuiteConfig
from harvesters.composite_harvester import CompositeHarvester
from .matcher import AssertionResult, evaluate_relation_expectation, evaluate_triples_and_sparql


class SuiteRunner:
    """Executes an RT TestSuiteConfig against live or mocked web resources."""

    def __init__(self, harvester: Optional[CompositeHarvester] = None):
        self.harvester = harvester or CompositeHarvester()

    def resolve_target_urls(self, test_config: TestCaseConfig, available_urls: Optional[List[str]] = None) -> List[str]:
        """Resolve all distinct target URLs matching explicit urls and pattern filters."""
        targets = set(test_config.targets.urls)

        if test_config.targets.patterns and available_urls:
            for pattern in test_config.targets.patterns:
                for candidate in available_urls:
                    if fnmatch.fnmatch(candidate, pattern) or (
                        pattern.startswith("^") and re.search(pattern, candidate)
                    ):
                        targets.add(candidate)

        return sorted(targets)

    def run_test_case(
        self,
        test_config: TestCaseConfig,
        client: Optional[httpx.Client] = None,
        available_urls: Optional[List[str]] = None,
    ) -> List[AssertionResult]:
        """Run all assertions for a single TestCaseConfig."""
        target_urls = self.resolve_target_urls(test_config, available_urls)
        results: List[AssertionResult] = []

        if not target_urls:
            return [
                AssertionResult(
                    case_name=f"rt_config [{test_config.name}]",
                    target_url="",
                    passed=True,
                    skipped=True,
                    skipped_message="No matching target URLs configured",
                    properties={"skipped": "true", "reason": "No matching target URLs configured"},
                )
            ]

        for url in target_urls:
            start_time = time.time()
            node = self.harvester.harvest(
                url,
                client=client,
                expand_linksets=test_config.expand_linksets,
            )
            duration = time.time() - start_time
            node.duration = duration

            has_expectations = bool(test_config.expect.relations or test_config.expect.min_triples is not None or test_config.expect.sparql_ask)

            if not has_expectations:
                # Basic reachability/harvest check
                results.append(
                    AssertionResult(
                        case_name=f"rt_harvest [{url}]",
                        target_url=url,
                        passed=node.error is None and node.status_code < 400,
                        error=node.error,
                        failure_message=f"HTTP status {node.status_code}" if node.status_code >= 400 else None,
                        failure_text=f"Harvest returned HTTP {node.status_code}" if node.status_code >= 400 else None,
                        stdout=f"GET {url}\nStatus: {node.status_code}\nDiscovered Links: {len(node.all_links)}",
                        stderr=node.error or "",
                        duration=duration,
                        properties={"url": url, "status_code": str(node.status_code)},
                    )
                )

            for exp in test_config.expect.relations:
                res = evaluate_relation_expectation(node, exp)
                res.duration = duration
                results.append(res)

            rdf_results = evaluate_triples_and_sparql(node, test_config.expect)
            for res in rdf_results:
                res.duration = duration
                results.append(res)

        for res in results:
            res.suite_name = test_config.name

        return results

    def run_suite(
        self,
        suite_config: TestSuiteConfig,
        client: Optional[httpx.Client] = None,
        available_urls: Optional[List[str]] = None,
    ) -> List[AssertionResult]:
        """Run all test cases in the test suite, including resolved pattern test cases."""
        all_results: List[AssertionResult] = []
        for test_config in suite_config.resolve_all_tests():
            case_results = self.run_test_case(
                test_config,
                client=client,
                available_urls=available_urls,
            )
            all_results.extend(case_results)
        return all_results

