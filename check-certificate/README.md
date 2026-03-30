# Check Certificate — Configuration Reference

## Overview

The certificate check test verifies the TLS certificate expiry for one or more URLs. For each URL, the test:

- Connects to the host on the configured port and retrieves the TLS certificate
- Checks whether the certificate has already expired
- Checks whether the certificate will expire within a configurable warning threshold

SSL verification is intentionally disabled when retrieving the certificate — this ensures that expired or otherwise invalid certificates can still be retrieved and evaluated rather than causing a connection failure before the check can run.

The test produces a failure if the certificate has expired, and a failure if it will expire within the configured threshold. Connection errors (DNS failure, timeout, unreachable host) are reported as errors rather than failures. Checking general HTTPS availability is the responsibility of the Resource Availability test.

---

## Local Testing

A `docker-compose.yml` is included in this directory for running the test locally without the orchestrator. It is intended as a working example — edit the environment variables to match your own URLs and threshold before running:

```bash
docker-compose up --build
```

The report will be written to `./reports/localtestrun_report.xml`.

---

## Configuration Parameters

### `urls`
**Required.** One or more URLs to check. The port is extracted from the URL if present, otherwise port 443 is used.

```yaml
urls:
  - https://example.com
  - https://other.org:8443/path
```

A bare string is also accepted without list syntax:

```yaml
urls: https://example.com
```

If absent or empty, the test is skipped entirely.

---

### `certificate-expiry-days`
**Optional.** The number of days before expiry at which the test should start warning. If the certificate expires within this many days, the test fails with a warning. Must be at least 0 — setting it to `0` disables the warning threshold and only fails on already-expired certificates.

Default: `30`

```yaml
certificate-expiry-days: 14
```

---

### `timeout`
**Optional.** Connection timeout in seconds when retrieving the certificate. Must be at least 1. Falls back to the default on invalid or out-of-range values.

Default: `30`

```yaml
timeout: 10
```

---

## Test Cases Produced

One test case is produced per URL:

| Test case | Always produced |
| --- | --- |
| `certificate_expiry [url]` | Yes |

The possible outcomes for each test case are:

| Outcome | Condition |
| --- | --- |
| Pass | Certificate is valid and does not expire within the threshold |
| Failure | Certificate will expire within `certificate-expiry-days` days |
| Failure | Certificate has already expired |
| Error | Certificate could not be retrieved (connection error, timeout, DNS failure) |
| Error | URL is malformed (no hostname, invalid port) |

---

## Example Configurations

### Minimal — default 30-day warning threshold
```yaml
tests:
  my-cert-check:
    image: ghcr.io/vliz-be-opsci/grmp-tests/check-certificate:latest
    config:
      urls:
        - https://example.com
```

### Strict — short warning threshold, custom timeout
```yaml
tests:
  my-cert-check:
    image: ghcr.io/vliz-be-opsci/grmp-tests/check-certificate:latest
    config:
      urls:
        - https://example.com
        - https://other.org:8443
      certificate-expiry-days: 60
      timeout: 10
```

### Expiry-only — only fail on actually expired certificates
```yaml
tests:
  my-cert-check:
    image: ghcr.io/vliz-be-opsci/grmp-tests/check-certificate:latest
    config:
      urls:
        - https://example.com
      certificate-expiry-days: 0
```