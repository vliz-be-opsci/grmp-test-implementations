#!/usr/bin/env python3
"""
RT-Test: Radical Transparency Web Linking and Profile Test Suite.
"""

from __future__ import annotations

import argparse
import os
import sys

# Ensure src/ directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from config.loader import (
    load_config_from_env,
    load_config_from_file,
    load_config_from_yaml,
)
from config.models import (
    ExpectationConfig,
    RelationExpectation,
    TargetConfig,
    TestCaseConfig,
    TestSuiteConfig,
)
from evaluator.runner import SuiteRunner
from reporter.console import print_flat_results, print_grouped_results
from reporter.junit import generate_junit_xml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Radical Transparency (RT) Web Linking & Profile Conformance Test Suite"
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to YAML test configuration file",
        default=os.environ.get("TEST_CONFIG_PATH"),
    )
    parser.add_argument(
        "-r", "--report",
        help="Path to output JUnit XML report",
        default=None,
    )
    parser.add_argument(
        "-u", "--urls",
        nargs="*",
        help="Ad-hoc list of URLs to test",
        default=None,
    )
    parser.add_argument(
        "--expect-rel",
        nargs="*",
        help="Expected link relations for ad-hoc URLs",
        default=["profile"],
    )
    parser.add_argument(
        "--diagrams",
        choices=["always", "on-failure", "never"],
        default=os.environ.get("RT_DIAGRAMS", "on-failure"),
        help="Control ASCII pattern diagram display in console (always, on-failure, never). Default: on-failure",
    )
    parser.add_argument(
        "--format",
        choices=["grouped", "flat", "compact"],
        default=os.environ.get("RT_FORMAT", "grouped"),
        help="Output formatting style: grouped (hierarchical test case view with carrier provenance), flat (detailed 1-liners), compact. Default: grouped",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    suite_name = os.environ.get("TS_NAME", "rt-test")
    provenance = os.environ.get("SPECIAL_SOURCE_FILE", "unknown")
    create_issue = os.environ.get("SPECIAL_CREATE_ISSUE", "false").lower() == "true"

    suite_config: TestSuiteConfig

    if args.config and os.path.isfile(args.config):
        print(f"Loading test suite from configuration file: {args.config}")
        suite_config = load_config_from_file(args.config)
        suite_config.name = suite_name
    elif args.urls:
        print(f"Running ad-hoc test for URLs: {args.urls}")
        relations = [RelationExpectation(rel=r, exists=True) for r in args.expect_rel]
        suite_config = TestSuiteConfig(
            name=suite_name,
            tests=[
                TestCaseConfig(
                    name="Ad-hoc URL Test",
                    targets=TargetConfig(urls=args.urls),
                    expand_linksets=True,
                    expect=ExpectationConfig(relations=relations),
                )
            ],
        )
    else:
        print("Loading test suite from environment variables...")
        suite_config = load_config_from_env()

    report_path = args.report
    if not report_path:
        report_dir = "/reports" if os.path.isdir("/reports") or not os.path.exists("./reports") else "./reports"
        report_path = f"{report_dir}/{suite_name}_report.xml"

    resolved_cases = suite_config.resolve_all_tests()
    print(f"Starting RT Test Suite: {suite_config.name}")
    print(f"Executing {len(resolved_cases)} test case definitions...")

    runner = SuiteRunner()
    results = runner.run_suite(suite_config)

    diagram_mode = args.diagrams.lower()
    fmt_mode = args.format.lower()
    if fmt_mode == "grouped":
        print_grouped_results(results, diagram_mode=diagram_mode)
    elif fmt_mode == "flat":
        print_flat_results(results, diagram_mode=diagram_mode, detailed=True)
    else:
        print_flat_results(results, diagram_mode=diagram_mode, detailed=False)

    failures = sum(1 for r in results if not r.passed and r.error is None and not r.skipped)
    errors = sum(1 for r in results if r.error is not None)
    skipped = sum(1 for r in results if r.skipped)
    passed = sum(1 for r in results if r.passed and not r.skipped)

    print(f"\nExecution finished: {len(results)} assertion(s) evaluated ({passed} passed, {failures} failed, {errors} error(s), {skipped} skipped).")
    print(f"Writing JUnit XML report to: {report_path}")

    extra_props = {}
    if getattr(suite_config, "version", None):
        extra_props["version"] = suite_config.version

    generate_junit_xml(
        suite_name=suite_config.name,
        results=results,
        output_file=report_path,
        provenance=provenance,
        create_issue=create_issue,
        extra_properties=extra_props,
    )

    print("Done.")
    return 0 if failures == 0 and errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
