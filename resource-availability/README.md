# Resource Availability — Configuration Reference

## Overview

The resource availability test checks whether one or more URLs are reachable and responding correctly. For each URL, the test performs:

- A **DNS resolution** check to verify the hostname resolves to an IP address
- An **HTTP availability** check (optional) — verifies the HTTP endpoint is reachable and returns a successful status code
- An **HTTPS availability** check (optional, enabled by default) — verifies the HTTPS endpoint is reachable and returns a successful status code

Redirects are followed manually up to a configurable limit. Redirect chains that cross the HTTP/HTTPS scheme boundary are treated as informational rather than failures — the test reports the redirect target but does not follow it further. SSL certificate validity can optionally be verified via the `verify-ssl` parameter, though in-depth certificate expiry checking is the responsibility of the Check Certificate test.

If DNS resolution fails for a URL, the HTTP and HTTPS availability checks for that URL are automatically skipped.

---

## Local Testing

A `docker-compose.yml` is included in this directory for running the test locally without the orchestrator. It is intended as a working example — edit the environment variables to match your own URLs and settings before running:

```bash
docker-compose up --build
```

The report will be written to `./reports/localtestrun_report.xml`.

---

## Configuration Parameters

### `urls`
**Required.** One or more URLs to test.

```yaml
urls:
  - https://example.com/stream
  - https://other.org/data
```

A bare string is also accepted without list syntax:

```yaml
urls: https://example.com
```

If absent or empty, the test is skipped entirely.

---

### `check-http-availability`
**Optional.** When `true`, performs an availability check on the HTTP version of each URL.

Default: `false`

```yaml
check-http-availability: true
```

---

### `check-https-availability`
**Optional.** When `true`, performs an availability check on the HTTPS version of each URL.

Default: `true`

```yaml
check-https-availability: true
```

---

### `max-redirects`
**Optional.** Maximum number of redirects to follow within the same scheme (HTTP→HTTP or HTTPS→HTTPS). Redirects that cross the scheme boundary (HTTP→HTTPS) are always stopped at the boundary regardless of this setting and reported as informational. Must be at least 0.

Default: `0`

```yaml
max-redirects: 3
```

---

### `verify-ssl`
**Optional.** When `true`, SSL certificates are verified for HTTPS requests. When `false`, certificate errors are ignored. Note that disabling SSL verification does not affect the DNS or HTTP checks — it only applies to HTTPS connections.

Default: `true`

```yaml
verify-ssl: false
```

---

### `timeout`
**Optional.** Request timeout in seconds. Must be at least 1. Falls back to the default on invalid or out-of-range values.

Default: `30`

```yaml
timeout: 10
```

---

## Test Cases Produced

For each URL the following test cases are produced, depending on configuration:

| Test case | Always produced | Condition |
| --- | --- | --- |
| `dns_resolution [url]` | Yes | — |
| `http_availability [url]` | No | `check-http-availability: true` |
| `https_availability [url]` | No | `check-https-availability: true` (default) |

If DNS resolution fails, the availability test cases are produced but marked as skipped.

---

## Example Configurations

### Minimal — HTTPS check only (default)
```yaml
tests:
  my-resource-check:
    image: ghcr.io/vliz-be-opsci/grmp-tests/resource-availability:latest
    config:
      urls:
        - https://example.com/stream
```

### Full — HTTP and HTTPS, redirect following, SSL verification disabled
```yaml
tests:
  my-resource-check:
    image: ghcr.io/vliz-be-opsci/grmp-tests/resource-availability:latest
    config:
      urls:
        - https://example.com/stream
        - https://other.org/data
      check-http-availability: true
      check-https-availability: true
      max-redirects: 3
      verify-ssl: false
      timeout: 10
```