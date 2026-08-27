"""
Configuration loader for RT YAML test definitions and environment variables.
"""

from __future__ import annotations

import ast
import os
import sys
from typing import Any, Dict, List, Optional
import yaml

from .models import (
    ExpectationConfig,
    PatternTestConfig,
    RelationExpectation,
    TargetConfig,
    TestCaseConfig,
    TestSuiteConfig,
)


def _process_raw_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Preprocess dictionary to handle pattern tests specified inside 'tests' or 'patterns'."""
    raw_tests = data.get("tests", [])
    raw_patterns = data.get("patterns", [])

    processed_tests: List[Any] = []
    processed_patterns: List[Any] = list(raw_patterns)

    for item in raw_tests:
        if isinstance(item, dict):
            # Check if this item is a pattern definition (has pattern/type and uris/roles, or no targets)
            has_pattern_key = bool(item.get("pattern") or item.get("type"))
            has_role_key = bool(item.get("uris") or item.get("roles"))
            is_pattern = has_pattern_key and (has_role_key or "targets" not in item)

            if is_pattern:
                processed_patterns.append(item)
            else:
                processed_tests.append(item)
        else:
            processed_tests.append(item)

    data["tests"] = processed_tests
    data["patterns"] = processed_patterns
    return data


def load_config_from_yaml(yaml_str: str) -> TestSuiteConfig:
    """Parse YAML string into a TestSuiteConfig instance."""
    data = yaml.safe_load(yaml_str)
    if not isinstance(data, dict):
        raise ValueError("Root of test configuration YAML must be a mapping/dictionary")
    processed = _process_raw_config(data)
    return TestSuiteConfig.model_validate(processed)


def load_config_from_file(file_path: str) -> TestSuiteConfig:
    """Load YAML test suite from a file path."""
    with open(file_path, "r", encoding="utf-8") as f:
        return load_config_from_yaml(f.read())


def _parse_list_env(name: str, default: Optional[List[str]] = None) -> List[str]:
    raw = os.environ.get(name)
    if raw is None:
        return default or []
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return [raw]
    if isinstance(parsed, str):
        return [parsed]
    if isinstance(parsed, (list, tuple)):
        return [v.strip() for v in parsed if isinstance(v, str) and v.strip()]
    return default or []


def load_config_from_env() -> TestSuiteConfig:
    """
    Resolve test configuration from environment variables.
    Checks:
    1. TEST_CONFIG_PATH: File path to a YAML config file.
    2. TEST_CONFIG_YAML: Raw YAML string content.
    3. Fallback: TEST_URLS (basic test case with profile relation check).
    """
    suite_name = os.environ.get("TS_NAME", "rt-test")

    config_path = os.environ.get("TEST_CONFIG_PATH")
    if config_path and os.path.isfile(config_path):
        config = load_config_from_file(config_path)
        config.name = suite_name
        return config

    config_yaml = os.environ.get("TEST_CONFIG_YAML")
    if config_yaml and config_yaml.strip():
        config = load_config_from_yaml(config_yaml)
        config.name = suite_name
        return config

    # Fallback to TEST_URLS environment variable
    urls = _parse_list_env("TEST_URLS")
    expected_rels = _parse_list_env("TEST_EXPECT_RELS", ["profile"])

    relations = [RelationExpectation(rel=rel, exists=True) for rel in expected_rels]

    fallback_test = TestCaseConfig(
        name="Environment URL Inspection",
        targets=TargetConfig(urls=urls),
        expand_linksets=True,
        expect=ExpectationConfig(relations=relations),
    )

    return TestSuiteConfig(
        name=suite_name,
        tests=[fallback_test] if urls else [],
    )
