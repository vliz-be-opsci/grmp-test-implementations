# CORS Compliance — Configuration Reference

## Overview

The CORS compliance test checks whether one or more URLs correctly advertise CORS support via HTTP response headers. It is designed for resources intended to be consumed by browser-based applications, such as LDES servers.

For each URL, the test performs:
- An HTTP `OPTIONS` preflight request to check `access-control-allow-origin`, `access-control-allow-methods`, and `access-control-allow-headers`
- An HTTP `GET` request to check `access-control-expose-headers`
- Optionally, an HTTP `GET` to the HTTP version of the URL to verify it redirects to HTTPS and that CORS headers survive the redirect

SSL certificate validity is intentionally not verified — that is the responsibility of the Check Certificate test.

---

## Local Testing

A `docker-compose.yml` is included in this directory for running the test locally without the orchestrator. It is intended as a working example — edit the environment variables to match your own URLs and expected headers before running:

```bash
docker-compose up
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

### `access-control-allow-origin`
**Optional.** Configures what the test expects in the `Access-Control-Allow-Origin` response header, and what `Origin` value is sent in the request.

This parameter has three modes:

#### Lenient mode (default — parameter absent)
The test sends the `probe-origin` as the request `Origin` and accepts either `*` or the probe origin in the response. Use this when you want to verify that a server is CORS-aware without caring about its specific policy.

```yaml
# omit access-control-allow-origin entirely
```

#### Wildcard mode
The test sends the `probe-origin` as the request `Origin` and asserts the response header is exactly `*`. Use this when the server is expected to be fully open to all origins.

```yaml
access-control-allow-origin: '*'
```

#### Specific origin mode
Provide one or more specific origins. For each origin, the test sends that origin as the request `Origin` and asserts it is reflected back exactly in the response. This works because a correctly configured server will only reflect an origin back if it is on its allowlist.

Note that `probe-origin` is ignored in this mode — the configured origin serves as both the sent value and the expected response.

```yaml
access-control-allow-origin:
  - https://vliz.be
  - https://marineregions.org
```

Mixing `*` with specific origins is invalid and will fall back to lenient mode.

---

### `access-control-allow-methods`
**Optional.** The HTTP methods the server is expected to advertise in the `Access-Control-Allow-Methods` response header. The configured methods must be a **subset** of what the server advertises — the server may advertise additional methods and the test will still pass.

Default: `GET`, `HEAD`, `OPTIONS`

```yaml
access-control-allow-methods:
  - GET
  - HEAD
  - OPTIONS
```

---

### `access-control-allow-headers`
**Optional.** The request headers the server is expected to advertise as allowed in the `Access-Control-Allow-Headers` response header (returned in response to an `OPTIONS` preflight). The configured headers must be a **subset** of what the server advertises. Comparison is case-insensitive.

Default: `Accept`

```yaml
access-control-allow-headers:
  - Accept
  - X-Custom-Header
```

---

### `access-control-expose-headers`
**Optional.** The response headers the server is expected to expose to browser scripts via `Access-Control-Expose-Headers` (returned in response to a `GET` request). The configured headers must be a **subset** of what the server advertises. Comparison is case-insensitive.

Note that CORS-safelisted response headers (`Cache-Control`, `Content-Language`, `Content-Length`, `Content-Type`, `Expires`, `Last-Modified`, `Pragma`) do not need to be explicitly exposed by the server, but some servers include them anyway. If `Content-Type` is in your configured list and the server does not explicitly expose it, the test will fail.

Default: `Content-Type`, `Link`

```yaml
access-control-expose-headers:
  - Content-Type
  - Link
```

---

### `https-redirect`
**Optional.** When `true`, the test additionally verifies that the HTTP version of each URL redirects to HTTPS, and that the `Access-Control-Allow-Origin` header is still present after the redirect. Useful for catching server misconfigurations where CORS headers are stripped during the redirect.

Default: `false`

```yaml
https-redirect: true
```

---

### `probe-origin`
**Optional.** The `Origin` header value sent in requests when using lenient or wildcard mode. Has no effect in specific origin mode, where the configured origin is used directly. Should be set to an origin that is representative of your actual client application.

Default: `https://vliz.be`

```yaml
probe-origin: https://marineregions.org
```

> **Note:** The test will skip with an error if `probe-origin` is the same origin as the URL being tested. Origin identity follows browser semantics: scheme + hostname + port must all match. For example, `http://example.com` and `https://example.com` are considered different origins and are both valid probe origins for `https://example.com`, but `https://example.com:443` is the same origin as `https://example.com` (identical default port) and will be rejected.

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
| `access_control_allow_origin [url] [lenient]` | Yes | When `access-control-allow-origin` is absent (lenient mode) |
| `access_control_allow_origin [url] [*]` | No | When `access-control-allow-origin: '*'` (wildcard mode) |
| `access_control_allow_origin [url] [origin]` | No | One per configured origin in specific origin mode |
| `access_control_allow_methods [url]` | No | `access-control-allow-methods` is configured |
| `access_control_allow_headers [url]` | No | `access-control-allow-headers` is configured |
| `access_control_expose_headers [url]` | No | `access-control-expose-headers` is configured |
| `https_redirect [url]` | No | `https-redirect: true` |

If the `probe-origin` is the same origin as the URL being tested, all test cases for that URL are replaced with a single skipped result explaining the misconfiguration.

---

## Example Configurations

### Minimal — lenient origin check, default headers
```yaml
test:
  cors-compliance:
    image: ghcr.io/grmp-tests/cors-compliance:latest
    config:
      urls:
        - https://example.com/stream
```

### Strict — assert wildcard, specific methods and headers, redirect check
```yaml
test:
  cors-compliance:
    image: ghcr.io/grmp-tests/cors-compliance:latest
    config:
      urls:
        - https://example.com/stream
      access-control-allow-origin: '*'
      access-control-allow-methods:
        - GET
        - HEAD
        - OPTIONS
      access-control-allow-headers:
        - Accept
      access-control-expose-headers:
        - Content-Type
        - Link
      https-redirect: true
      probe-origin: https://vliz.be
      timeout: 30
```

### Multi-origin — verify specific origins are whitelisted
```yaml
test:
  cors-compliance:
    image: ghcr.io/grmp-tests/cors-compliance:latest
    config:
      urls:
        - https://example.com/stream
      access-control-allow-origin:
        - https://vliz.be
        - https://marineregions.org
```