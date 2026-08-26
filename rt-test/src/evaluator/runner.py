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
                    case_name=f"{test_config.name}: No target URLs resolved",
                    target_url="",
                    passed=True,
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

            prefix = f"[{url}] "

            for exp in test_config.expect.relations:
                res = evaluate_relation_expectation(node, exp, case_prefix=prefix)
                res.duration = duration
                results.append(res)

            rdf_results = evaluate_triples_and_sparql(node, test_config.expect, case_prefix=prefix)
            for res in rdf_results:
                res.duration = duration
                results.append(res)

        return results

    def run_suite(
        self,
        suite_config: TestSuiteConfig,
        client: Optional[httpx.Client] = None,
        available_urls: Optional[List[str]] = None,
    ) -> List[AssertionResult]:
        """Run all test cases in the test suite."""
        all_results: List[AssertionResult] = []
        for test_config in suite_config.tests:
            case_results = self.run_test_case(
                test_config,
                client=client,
                available_urls=available_urls,
            )
            all_results.extend(case_results)
        return all_results
