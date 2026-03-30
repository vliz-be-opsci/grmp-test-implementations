# Input Echo Test — Configuration Reference

## Overview

The input echo test is a minimal demonstration test for the GRMP framework. It does not test any external resource — instead it inspects its own `TEST_*` environment variables and verifies that they are present and non-empty. It is intended as a quick sanity check that the orchestrator is correctly passing configuration parameters to test containers, and as a reference example for understanding the basic structure of a GRMP test.

Two test cases are produced:

- `get_env_test` — verifies that at least one `TEST_*` parameter is configured
- `check_emptiness_test` — verifies that none of the configured `TEST_*` parameters have an empty or `None` value (skipped if `get_env_test` fails)

---

## Local Testing

A `docker-compose.yml` is included in this directory for running the test locally without the orchestrator. The included example deliberately sets one empty variable (`TEST_EMPTY_VAR`) to demonstrate what a failure looks like:

```bash
docker-compose up --build
```

The report will be written to `./reports/localtestrun_report.xml`.

---

## Configuration Parameters

Unlike the other GRMP tests, the input echo test has no fixed configuration parameters. It dynamically collects **all** `TEST_*` environment variables present at runtime and treats them as its input. The keys and values are echoed to the test output and included as suite properties in the JUnit report.

The only meaningful distinction is between parameters that are present and non-empty (pass) versus absent entirely (fail `get_env_test`) or present but empty (fail `check_emptiness_test`).

---

## Test Cases Produced

| Test case | Always produced | Condition |
| --- | --- | --- |
| `get_env_test` | Yes | — |
| `check_emptiness_test` | Yes* | Skipped if `get_env_test` fails |

\* The test case is always produced but may be skipped.

### Outcomes

**`get_env_test`**

| Outcome | Condition |
| --- | --- |
| Pass | At least one `TEST_*` variable is set |
| Failure | No `TEST_*` variables are configured at all |

**`check_emptiness_test`**

| Outcome | Condition |
| --- | --- |
| Pass | All `TEST_*` variables have non-empty values |
| Failure | One or more `TEST_*` variables are empty, whitespace-only, or the string `"None"` |
| Skipped | `get_env_test` failed or errored |

---

## Example Configuration

```yaml
tests:
  my-echo-test:
    image: ghcr.io/vliz-be-opsci/grmp-tests/input-echo-test:latest
    config:
      some-param: hello
      another-param: world
```

This will produce two passing test cases, with `TEST_SOME-PARAM=hello` and `TEST_ANOTHER-PARAM=world` passed to the container.