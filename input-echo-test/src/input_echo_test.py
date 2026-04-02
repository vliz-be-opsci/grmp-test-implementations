#!/usr/bin/env python3
"""
Input Echo Test
Checks the presence and validity of TEST_* configuration parameters.

The following test cases are produced:
  - get_env_test        checks that at least one TEST_* parameter is configured
  - check_emptiness_test  checks that none of the TEST_* parameters have an empty or None value
                          (skipped if get_env_test fails)
"""

import contextlib
import io
import os
import sys
import time
from datetime import datetime, timezone

from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped


# ---------------------------------------------------------------------------
# Output capture
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def capture_output():
    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        yield out, err


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------

def parse_config():
    """
    Collect all TEST_* environment variables and provenance.
    Returns a dict with all TEST_* keys (lowercased, prefix stripped) as
    config parameters, plus provenance from SPECIAL_SOURCE_FILE.
    """
    params = {}
    for key, value in os.environ.items():
        if key.startswith("TEST_"):
            params[key[len("TEST_"):].lower()] = value

    return {
        "params": params,
        "provenance": os.environ.get("SPECIAL_SOURCE_FILE", "unknown"),
        "create_issue": os.environ.get("SPECIAL_CREATE_ISSUE", "false").lower() == "true",
    }


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _result(case_name, *, failure_message=None, failure_text=None,
            error=None, skipped=False, skipped_message="",
            stdout="", stderr="", duration=0.0, properties=None):
    return {
        "case_name": case_name,
        "duration": duration,
        "error": error,
        "failure_message": failure_message,
        "failure_text": failure_text,
        "properties": properties if properties is not None else {},
        "skipped": skipped,
        "skipped_message": skipped_message,
        "stdout": stdout,
        "stderr": stderr,
    }


def skipped_test(case_name, reason):
    return _result(case_name, skipped=True, skipped_message=reason)


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def get_env_test(params):
    """
    Check that at least one TEST_* parameter is configured.
    Records all parameters and their count as test case properties.
    """
    start = time.time()
    with capture_output() as (out, err):
        properties = dict(params)

        for key, value in params.items():
            print(f"Found: TEST_{key.upper()} = {value}")

        print(f"test_parameter_count: {len(params)}")

        if len(params) == 0:
            failure_message = "No test parameters found"
            failure_text = "No TEST_* environment variables are configured."
            print("No TEST_* parameters found", file=sys.stderr)
        else:
            failure_message = None
            failure_text = None

    duration = time.time() - start
    return _result(
        "get_env_test",
        failure_message=failure_message,
        failure_text=failure_text,
        stdout=out.getvalue(),
        stderr=err.getvalue(),
        duration=duration,
        properties=properties,
    )


def check_emptiness_test(params):
    """
    Check that none of the TEST_* parameters have an empty or None value.
    """
    start = time.time()
    with capture_output() as (out, err):
        empty_vars = []
        for key, value in params.items():
            if value is None or value.strip() == "" or value == "None":
                empty_vars.append(key)
                print(f"Found empty value: TEST_{key.upper()} = {value!r}")

        print(f"empty_test_parameter_count: {len(empty_vars)}")

        if empty_vars:
            failure_message = "Empty test parameters found"
            failure_text = "\n".join(sorted(empty_vars))
        else:
            failure_message = None
            failure_text = None

    duration = time.time() - start
    return _result(
        "check_emptiness_test",
        failure_message=failure_message,
        failure_text=failure_text,
        stdout=out.getvalue(),
        stderr=err.getvalue(),
        duration=duration,
    )


def check_secrets_test():
    """
    Check that at least one SECRET_* environment variable is configured and non-empty.
    Lists the names of found secrets in stdout — never their values.
    """
    start = time.time()
    with capture_output() as (out, err):
        secret_keys = [
            key for key, value in os.environ.items()
            if key.startswith("SECRET_") and value and value.strip() and value != "None"
        ]

        for key in sorted(secret_keys):
            print(f"Found secret: {key}")

        print(f"secret_count: {len(secret_keys)}")

        if len(secret_keys) == 0:
            failure_message = "No secrets found"
            failure_text = "No non-empty SECRET_* environment variables are configured."
            print("No SECRET_* variables found", file=sys.stderr)
        else:
            failure_message = None
            failure_text = None

    duration = time.time() - start
    return _result(
        "check_secrets_test",
        failure_message=failure_message,
        failure_text=failure_text,
        stdout=out.getvalue(),
        stderr=err.getvalue(),
        duration=duration,
    )


# ---------------------------------------------------------------------------
# JUnit report
# ---------------------------------------------------------------------------

def create_junit_report(suite_name, results, output_file, provenance,
                        suite_properties=None):
    suite = TestSuite(suite_name)
    suite.timestamp = datetime.now(timezone.utc).isoformat()
    if suite_properties is None:
        suite_properties = {}
    total_time = 0.0
    added_properties = set()

    for result in results:
        case = TestCase(result["case_name"], classname=suite_name)
        case.time = result["duration"]
        total_time += result["duration"]

        for key, value in result["properties"].items():
            if key not in added_properties:
                suite.add_property(key, value)
                added_properties.add(key)

        if result["skipped"]:
            case.result = [Skipped(message=result["skipped_message"])]
        else:
            if result["error"] is not None:
                err = Error(message="Unexpected error")
                err.text = str(result["error"])
                case.result = [err]
                if result.get("stderr"):
                    case.system_err = result["stderr"]
            elif result["failure_message"]:
                failure = Failure(message=result["failure_message"])
                failure.text = result["failure_text"]
                case.result = [failure]
            if result.get("stdout"):
                case.system_out = result["stdout"]

        suite.add_testcase(case)

    suite.add_property("provenance", provenance)
    suite.add_property("create-issue", str(suite_properties.get("create_issue", False)).lower())
    suite.time = total_time
    xml = JUnitXml()
    xml.add_testsuite(suite)
    xml.write(output_file)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    suite_name = os.environ.get("TS_NAME", "input-echo")
    config = parse_config()
    params = config["params"]

    result_get_env = get_env_test(params)

    if result_get_env["failure_message"] or result_get_env["error"]:
        results = [
            result_get_env,
            skipped_test("check_emptiness_test",
                         "Skipped because get_env_test did not pass."),
            check_secrets_test(),
        ]
    else:
        results = [result_get_env, check_emptiness_test(params), check_secrets_test()]

    report_path = f"/reports/{suite_name}_report.xml"
    create_junit_report(
        suite_name, results, output_file=report_path,
        provenance=config["provenance"],
        suite_properties=config,
    )