#!/usr/bin/env python3
"""
Unit tests for input_echo.py

Run with (from input-echo/ root):
    pip install pytest junitparser
    pytest tests/test_input_echo.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from input_echo_test import (
    parse_config,
    get_env_test,
    check_emptiness_test,
    check_secrets_test,
    create_junit_report,
    skipped_test,
)


# ---------------------------------------------------------------------------
# parse_config
# ---------------------------------------------------------------------------

class TestParseConfig:
    ENV_KEYS_PREFIX = "TEST_"

    def _clean_test_vars(self, monkeypatch):
        for key in list(os.environ.keys()):
            if key.startswith("TEST_"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.delenv("SPECIAL_SOURCE_FILE", raising=False)
        monkeypatch.delenv("SPECIAL_CREATE_ISSUE", raising=False)

    def test_collects_test_prefixed_vars(self, monkeypatch):
        self._clean_test_vars(monkeypatch)
        monkeypatch.setenv("TEST_URLS", "https://example.com")
        monkeypatch.setenv("TEST_TIMEOUT", "30")
        config = parse_config()
        assert config["params"]["urls"] == "https://example.com"
        assert config["params"]["timeout"] == "30"

    def test_ignores_non_test_vars(self, monkeypatch):
        self._clean_test_vars(monkeypatch)
        monkeypatch.setenv("OTHER_VAR", "value")
        config = parse_config()
        assert "other_var" not in config["params"]

    def test_strips_test_prefix_and_lowercases_key(self, monkeypatch):
        self._clean_test_vars(monkeypatch)
        monkeypatch.setenv("TEST_MY_PARAM", "hello")
        config = parse_config()
        assert "my_param" in config["params"]

    def test_empty_params_when_no_test_vars(self, monkeypatch):
        self._clean_test_vars(monkeypatch)
        config = parse_config()
        assert config["params"] == {}

    def test_provenance_from_special_source_file(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_SOURCE_FILE", "my-config.yaml")
        assert parse_config()["provenance"] == "my-config.yaml"

    def test_provenance_defaults_to_unknown(self, monkeypatch):
        monkeypatch.delenv("SPECIAL_SOURCE_FILE", raising=False)
        assert parse_config()["provenance"] == "unknown"

    def test_create_issue_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv("SPECIAL_CREATE_ISSUE", raising=False)
        assert parse_config()["create_issue"] is False

    def test_create_issue_true_when_set(self, monkeypatch):
        monkeypatch.setenv("SPECIAL_CREATE_ISSUE", "true")
        assert parse_config()["create_issue"] is True


# ---------------------------------------------------------------------------
# get_env_test
# ---------------------------------------------------------------------------

class TestGetEnvTest:
    def test_passes_when_params_present(self):
        result = get_env_test({"urls": "https://example.com", "timeout": "30"})
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_fails_when_no_params(self):
        result = get_env_test({})
        assert result["failure_message"] is not None
        assert "No test parameters" in result["failure_message"]

    def test_records_parameter_count_in_stdout(self):
        result = get_env_test({"urls": "https://example.com", "timeout": "30"})
        assert "test_parameter_count: 2" in result["stdout"]

    def test_zero_count_in_stdout_when_no_params(self):
        result = get_env_test({})
        assert "test_parameter_count: 0" in result["stdout"]

    def test_params_included_as_properties(self):
        result = get_env_test({"urls": "https://example.com"})
        assert result["properties"]["urls"] == "https://example.com"

    def test_failure_goes_to_stderr(self):
        result = get_env_test({})
        assert result["stderr"] != ""

    def test_params_logged_to_stdout(self):
        result = get_env_test({"timeout": "30"})
        assert "TEST_TIMEOUT" in result["stdout"]

    def test_case_name_is_correct(self):
        result = get_env_test({})
        assert result["case_name"] == "get_env_test"


# ---------------------------------------------------------------------------
# check_emptiness_test
# ---------------------------------------------------------------------------

class TestCheckEmptinessTest:
    def test_passes_when_all_params_non_empty(self):
        result = check_emptiness_test({"urls": "https://example.com", "timeout": "30"})
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_fails_when_param_is_empty_string(self):
        result = check_emptiness_test({"urls": ""})
        assert result["failure_message"] is not None
        assert "urls" in result["failure_text"]

    def test_fails_when_param_is_whitespace(self):
        result = check_emptiness_test({"urls": "   "})
        assert result["failure_message"] is not None

    def test_fails_when_param_is_none_string(self):
        result = check_emptiness_test({"urls": "None"})
        assert result["failure_message"] is not None

    def test_empty_count_in_stdout_reflects_failures(self):
        result = check_emptiness_test({"urls": "", "timeout": ""})
        assert "empty_test_parameter_count: 2" in result["stdout"]

    def test_zero_empty_count_in_stdout_when_all_valid(self):
        result = check_emptiness_test({"urls": "https://example.com"})
        assert "empty_test_parameter_count: 0" in result["stdout"]

    def test_empty_params_logged_to_stdout(self):
        result = check_emptiness_test({"urls": ""})
        assert "TEST_URLS" in result["stdout"]

    def test_case_name_is_correct(self):
        result = check_emptiness_test({})
        assert result["case_name"] == "check_emptiness_test"

    def test_failure_text_lists_empty_vars_sorted(self):
        result = check_emptiness_test({"b_param": "", "a_param": ""})
        lines = result["failure_text"].splitlines()
        assert lines == sorted(lines)


# ---------------------------------------------------------------------------
# check_secrets_test
# ---------------------------------------------------------------------------

class TestCheckSecretsTest:
    def test_passes_when_secret_present(self, monkeypatch):
        monkeypatch.setenv("SECRET_MY_API_KEY", "supersecret")
        result = check_secrets_test()
        assert result["failure_message"] is None
        assert result["error"] is None

    def test_fails_when_no_secrets(self, monkeypatch):
        for key in list(os.environ.keys()):
            if key.startswith("SECRET_"):
                monkeypatch.delenv(key, raising=False)
        result = check_secrets_test()
        assert result["failure_message"] is not None
        assert "No secrets found" in result["failure_message"]

    def test_empty_secret_not_counted(self, monkeypatch):
        for key in list(os.environ.keys()):
            if key.startswith("SECRET_"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("SECRET_EMPTY", "")
        result = check_secrets_test()
        assert result["failure_message"] is not None

    def test_secret_name_in_stdout(self, monkeypatch):
        monkeypatch.setenv("SECRET_MY_API_KEY", "supersecret")
        result = check_secrets_test()
        assert "SECRET_MY_API_KEY" in result["stdout"]

    def test_secret_value_not_in_stdout(self, monkeypatch):
        monkeypatch.setenv("SECRET_MY_API_KEY", "supersecret")
        result = check_secrets_test()
        assert "supersecret" not in result["stdout"]

    def test_secret_count_in_stdout(self, monkeypatch):
        for key in list(os.environ.keys()):
            if key.startswith("SECRET_"):
                monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("SECRET_KEY1", "val1")
        monkeypatch.setenv("SECRET_KEY2", "val2")
        result = check_secrets_test()
        assert "secret_count: 2" in result["stdout"]

    def test_no_properties(self, monkeypatch):
        monkeypatch.setenv("SECRET_MY_API_KEY", "supersecret")
        result = check_secrets_test()
        assert result["properties"] == {}

    def test_case_name_is_correct(self, monkeypatch):
        result = check_secrets_test()
        assert result["case_name"] == "check_secrets_test"

    def test_failure_goes_to_stderr(self, monkeypatch):
        for key in list(os.environ.keys()):
            if key.startswith("SECRET_"):
                monkeypatch.delenv(key, raising=False)
        result = check_secrets_test()
        assert result["stderr"] != ""


# ---------------------------------------------------------------------------
# skipped_test
# ---------------------------------------------------------------------------

class TestSkippedTest:
    def test_returns_skipped_result(self):
        result = skipped_test("check_emptiness_test", "reason")
        assert result["skipped"] is True
        assert result["skipped_message"] == "reason"
        assert result["case_name"] == "check_emptiness_test"
        assert result["failure_message"] is None
        assert result["error"] is None


# ---------------------------------------------------------------------------
# create_junit_report
# ---------------------------------------------------------------------------

class TestCreateJunitReport:
    def _result(self, name="get_env_test", failure=False, skipped=False, error=False):
        return {
            "case_name": name,
            "duration": 0.5,
            "error": "some error" if error else None,
            "failure_message": "fail msg" if failure else None,
            "failure_text": "fail detail" if failure else None,
            "properties": {"test_parameter_count": "2"},
            "skipped": skipped,
            "skipped_message": "reason" if skipped else "",
            "stdout": "some output",
            "stderr": "some err" if error else "",
        }

    def test_creates_xml_file(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, "prov")
        assert os.path.exists(out)

    def test_failure_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(failure=True)], out, "prov")
        assert "failure" in open(out).read().lower()

    def test_skipped_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(skipped=True)], out, "prov")
        assert "skipped" in open(out).read().lower()

    def test_error_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(error=True)], out, "prov")
        assert "error" in open(out).read().lower()

    def test_create_issue_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, "prov",
                            suite_properties={"create_issue": True})
        assert 'name="create-issue" value="true"' in open(out).read()

    def test_provenance_present_in_xml(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result()], out, "my-provenance-value")
        assert "my-provenance-value" in open(out).read()

    def test_stderr_present_on_error(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(error=True)], out, "prov")
        assert "some err" in open(out).read()

    def test_stderr_absent_on_failure(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [self._result(failure=True)], out, "prov")
        assert "some err" not in open(out).read()

    def test_properties_deduplicated(self, tmp_path):
        out = str(tmp_path / "report.xml")
        # Two results with the same property value
        results = [self._result("t1"), self._result("t2")]
        create_junit_report("suite", results, out, "prov")
        content = open(out).read()
        # Property should appear only once
        assert content.count('name="test_parameter_count"') == 1

    def test_suite_time_equals_sum_of_durations(self, tmp_path):
        from junitparser import JUnitXml as JX
        out = str(tmp_path / "report.xml")
        results = [self._result("t1"), self._result("t2")]  # 2 × 0.5s = 1.0s
        create_junit_report("suite", results, out, "prov")
        xml = JX.fromfile(out)
        for suite in xml:
            assert abs(suite.time - 1.0) < 0.001

    def test_empty_results_still_creates_file(self, tmp_path):
        out = str(tmp_path / "report.xml")
        create_junit_report("suite", [], out, "prov")
        assert os.path.exists(out)