# Content Negotiation — Configuration Reference

## Overview

The content negotiation test verifies that one or more URLs correctly honour HTTP content negotiation via the `Accept` request header. For each URL and configured `Accept` header value, the test:

- Sends a `GET` request with the configured `Accept` header
- Asserts the response returns a `2xx` status code
- Asserts the response `Content-Type` matches the requested type(s)
- Optionally attempts to parse the response body using rdflib to verify it conforms to its advertised content type

This test is primarily aimed at resources that serve RDF or linked data formats, though it can be used for any content type.

---

## Local Testing

A `docker-compose.yml` is included in this directory for running the test locally without the orchestrator. It is intended as a working example — edit the environment variables to match your own URLs and `Accept` headers before running:

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

### `accept-headers`
**Required.** One or more `Accept` header values to test. Each value is tested independently against every URL, producing a separate test case per URL + Accept header combination.

A single simple type performs an exact match against the response `Content-Type`:

```yaml
accept-headers:
  - text/turtle
  - application/ld+json
```

A complex header containing multiple types with quality weights is also supported. In this case the response `Content-Type` must be one of the listed types (excluding `*/*`):

```yaml
accept-headers:
  - 'application/ld+json, application/trig;q=0.98, text/turtle;q=0.95, application/n-quads;q=0.9, */*;q=0.1'
```

Using `*/*` as the sole `Accept` value accepts any response `Content-Type` without asserting a specific type.

If absent, the test is skipped entirely.

---

### `check-response-body-conformity`
**Optional.** When `true`, an additional body conformity test case is produced for each URL + Accept header combination. The response body is parsed using rdflib to verify it actually conforms to the advertised content type. Body conformity is only checked for known RDF content types — non-RDF types are skipped.

The supported RDF types for body conformity checking are: `text/turtle`, `application/ld+json`, `application/trig`, `application/n-quads`, `application/n-triples`, `application/rdf+xml`, `text/n3`.

If the content negotiation test for a given combination failed or errored, the body conformity test for that combination is automatically skipped.

When absent or set to any value other than `true` or `false`, body conformity checking is disabled.

Default: disabled

```yaml
check-response-body-conformity: true
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

For each URL + Accept header combination, the following test cases are produced:

| Test case | Always produced | Condition |
| --- | --- | --- |
| `content_negotiation [url] [accept]` | Yes | — |
| `body_conformity [url] [accept]` | No | `check-response-body-conformity: true` |

The `body_conformity` test case is skipped when:
- The corresponding `content_negotiation` test failed or errored
- The response `Content-Type` is not a supported RDF type

---

## Example Configurations

### Minimal — single content type per URL
```yaml
tests:
  my-cn-check:
    image: ghcr.io/vliz-be-opsci/grmp-tests/content-negotiation:latest
    config:
      urls:
        - https://example.com/data
      accept-headers:
        - text/turtle
        - application/ld+json
```

### Full — complex Accept header with body conformity checking
```yaml
tests:
  my-cn-check:
    image: ghcr.io/vliz-be-opsci/grmp-tests/content-negotiation:latest
    config:
      urls:
        - https://example.com/data
        - https://other.org/feed
      accept-headers:
        - text/turtle
        - 'application/ld+json, application/trig;q=0.98, text/turtle;q=0.95, */*;q=0.1'
      check-response-body-conformity: true
      timeout: 15
```