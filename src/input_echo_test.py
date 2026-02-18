#!/usr/bin/env python3
"""
Input Echo Test
A simple worker that creates a jUnit XML report containing the input parameters and checks whether any of them are empty.
"""

import os
from datetime import datetime, timezone
import time
from junitparser import TestCase, TestSuite, JUnitXml, Failure, Error, Skipped

def create_junit_report(test_suite_name, results, output_file="echo_report.xml"):
    """Create a jUnit XML report with input parameters using junitparser."""

    if results:
        suite = TestSuite(test_suite_name)
        suite.timestamp = datetime.now(timezone.utc).isoformat()
        total_time = 0.0

        for result in results:
            case = TestCase(result["case_name"], classname=test_suite_name)
            case.time = result["duration"]
            total_time += result["duration"]

            for key, value in result["properties"].items():
                suite.add_property(key, value)
            
            if result.get("skipped"):
                skipped = Skipped(message=result.get("skipped_message", "Skipped"))
                case.result = skipped
            elif result["error"] is not None:
                err = Error(message="Unexpected exception")
                err.text = str(result["error"])
                case.result = err
            elif result["failure_message"]:
                failure = Failure(message=result["failure_message"])
                failure.text = result["failure_text"]
                case.result = failure

            suite.add_testcase(case)
        
        suite.time = total_time

        xml = JUnitXml()
        xml.add_testsuite(suite)
        xml.write(output_file)

def check_emptiness_test():
    """Check whether TEST_ environment variables are empty or whitespace."""
    start = time.time()
    error = None
    failure_message = None
    failure_text = None
    properties = {}
    skip_reason = ""

    try:
        empty_vars = []

        for key, value in os.environ.items():
            if not key.startswith("TEST_"):
                continue
            elif value is None or value.strip() == "" or value == "None":
                empty_vars.append(key[len("TEST_"):].lower())

        properties["empty_test_parameter_count"] = str(len(empty_vars))

        if empty_vars:
            failure_message = "Empty test parameters found"
            failure_text = "\n".join(sorted(empty_vars))

    except Exception as exc:
        error = exc

    duration = time.time() - start

    source_file = os.environ.get("SPECIAL_SOURCE_FILE")
    if source_file:
        properties["source_file"] = source_file

    return {
        "case_name": "check_emptiness_test",
        "properties": properties,
        "duration": duration,
        "error": error,
        "failure_message": failure_message,
        "failure_text": failure_text,
        "skipped": False,
        "skipped_message": skip_reason
    }

def get_env_test():
    """Collect TEST_ environment variables."""
    start_time = time.time()
    error = None
    failure_message = None
    failure_text = None
    properties = {}
    skip_reason = ""

    try:
        for key, value in os.environ.items():
            if not key.startswith("TEST_"):
                continue
            else:
                properties[key[len("TEST_"):].lower()] = value
    except Exception as exc:
        error = exc

    env_var_count = len(properties)
    properties["test_parameter_count"] = str(env_var_count)

    if env_var_count == 0:
        failure_message = "No test parameters found"
        failure_text = ""

    duration = time.time() - start_time

    source_file = os.environ.get("SPECIAL_SOURCE_FILE")
    if source_file:
        properties["source_file"] = source_file

    return {
        "case_name": "get_env_test", 
        "properties": properties,
        "duration": duration,
        "error": error,
        "failure_message": failure_message,
        "failure_text": failure_text,
        "skipped": False,
        "skipped_message": skip_reason
    }

def skipped_test(case_name, reason="Test skipped"):
    """
    Return a dictionary in the same format as normal tests
    but indicating that the test was skipped.
    """
    return {
        "case_name": case_name,
        "duration": 0.0,
        "error": None,
        "failure_message": None,
        "failure_text": None,
        "properties": {},
        "skipped": True,
        "skipped_message": reason,
    }

if __name__ == '__main__':
    test_suite_name = os.getenv("TS_NAME")

    if test_suite_name:
        result_get_env = get_env_test()
        if result_get_env.get("failure_message") or result_get_env.get("error"):
            skip_reason = "Failure or error within the get_env_test"
            results = [result_get_env, skipped_test("check_emptiness_test", skip_reason)]
        else:
            result_empty = check_emptiness_test()
            results = [result_get_env, result_empty]
    else:
        skip_reason = "TS_NAME not set"
        test_suite_name = "unknown"
        results = [skipped_test("get_env_test", skip_reason), skipped_test("check_emptiness_test", skip_reason)]
    
    report_path = f'/reports/{test_suite_name}_report.xml'
    create_junit_report(test_suite_name, results, output_file=report_path)
