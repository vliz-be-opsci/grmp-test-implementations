# WRX Test — Configuration Reference

## Overview

The WRX test uses [`wrx`](https://github.com/cedricdcc/wrx) through a JavaScript helper to discover RDF for each configured URL. The helper is invoked from Python via subprocess, and the returned RDF is parsed again in Python to count triples and validate a basic SPARQL query.

Per URL, one JUnit test case is produced:

- `wrx_triples [url]`

## Configuration Parameters

- `URLS` (required): array of URLs to check
- `MIN-TRIPLES` (required): minimum number of triples that must be found per URL

Example orchestrator config:

```yaml
tests:
  wrx-test:
    image: ghcr.io/vliz-be-opsci/grmp-tests/wrx-test:latest
    config:
      urls:
        - https://example.org
      min-triples: 1
```

## Local Testing

```bash
docker-compose up --build
```

The JUnit report is written to `./reports/localtestrun_report.xml`.
