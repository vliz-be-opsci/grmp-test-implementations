# RT-Test — Radical Transparency Web Linking & Profile Conformance

## Overview

The `rt-test` suite validates web resources and digital assets against the **Radical Transparency (RT)** specifications defined in the [EOSC Semantic Interoperability Proposals](https://github.com/eosc-semantic-interop/if-solutions-proposals).

It discovers and validates web link relations and conformity-to-profile declarations across:
- **HTTP `Link` headers** ([RFC 8288](https://www.rfc-editor.org/info/rfc8288))
- **Linkset documents** (`application/linkset` and `application/linkset+json` - [RFC 9264](https://www.rfc-editor.org/info/rfc9264))
- **Hostwide discovery** (`sitemap.xml` with `<xhtml:link>` / ResourceSync `<rs:ln>`, and `robots.txt`)
- **HTML `<link>` tags** in response payloads
- **RDF Knowledge Graph mapping** (`rdflib`) using strict IANA URI predicates (`https://www.iana.org/assignments/relation/{rel}`)

---

## Curated RT Link Relations Catalog

| Relation (`rel`) | Specification / Context | Role in RT Patterns & Meaning | Example Link |
| :--- | :--- | :--- | :--- |
| **`profile`** | [RFC 6906](https://www.rfc-editor.org/info/rfc6906) | **RT-P01 Profile Declaration**: Declares conformance to a profile URI. | `Link: <https://example.org/profiles/v1>; rel="profile"` |
| **`http://schema.org/hasPart`** | Schema.org | **RT-P02 Profile Composition**: Declares member sub-profiles composed inside a parent composite profile. | `Link: <https://example.org/profiles/partA>; rel="http://schema.org/hasPart"` |
| **`http://schema.org/isPartOf`** | Schema.org | **RT-P02 Profile Composition**: Inverse relation indicating a sub-profile belongs to a parent profile. | `Link: <https://example.org/profiles/root>; rel="http://schema.org/isPartOf"` |
| **`linkset`** | [RFC 9264](https://www.rfc-editor.org/info/rfc9264) | **RT-P08 External Linksets**: Points to a dedicated linkset document exposing relations for the resource. | `Link: </.well-known/linkset>; rel="linkset"; type="application/linkset+json"` |
| **`describedby`** | [RFC 8288](https://www.rfc-editor.org/info/rfc8288) / Signposting | **RT-P04 No Landing Page / Metadata**: Links to descriptive metadata representations (JSON-LD, Turtle, etc.). | `Link: </meta/123.jsonld>; rel="describedby"; type="application/ld+json"` |
| **`item`** | [RFC 6573](https://www.rfc-editor.org/info/rfc6573) | **RT-P07 Catalog Assistance & RT-P03 Conneg**: Links a catalog or sitemap to a member resource. | `Link: </dataset/123>; rel="item"` |
| **`collection`** | [RFC 6573](https://www.rfc-editor.org/info/rfc6573) | **RT-P07 Catalog Assistance**: Links an item back to its parent collection / catalog. | `Link: </catalog>; rel="collection"` |
| **`cite-as`** | [RFC 8574](https://www.rfc-editor.org/info/rfc8574) | **RT-P04 Persistent Identifier**: Permanent citation identifier for the asset (DOI, Handle, URN). | `Link: <https://doi.org/10.1234/example>; rel="cite-as"` |
| **`type`** | [RFC 8288](https://www.rfc-editor.org/info/rfc8288) | **RT-P04 Type Hint**: Declares the conceptual / RDF type of the resource (e.g. `dcat:Dataset`). | `Link: <http://schema.org/Dataset>; rel="type"` |
| **`alternate`** | [RFC 8288](https://www.rfc-editor.org/info/rfc8288) | **RT-P03 Content Negotiation Menu**: Links to alternate format/profile representations. | `Link: </data.json>; rel="alternate"; type="application/json"; profile="https://example.org/p1"` |
| **`author`** | [RFC 8288](https://www.rfc-editor.org/info/rfc8288) / Signposting | **Signposting / Attribution**: Points to author/creator identity (e.g. ORCID URI). | `Link: <https://orcid.org/0000-0002-1825-0097>; rel="author"` |
| **`license`** | [RFC 8288](https://www.rfc-editor.org/info/rfc8288) / Signposting | **Signposting / Rights**: Points to the legal license terms applicable to the resource. | `Link: <https://spdx.org/licenses/CC-BY-4.0.html>; rel="license"` |
| **`latest-version`** | [RFC 5829](https://www.rfc-editor.org/info/rfc5829) | **Versioning**: Points to the latest/current version of a versioned resource or profile. | `Link: <https://example.org/dataset/latest>; rel="latest-version"` |
| **`service-desc`** | [RFC 8631](https://www.rfc-editor.org/info/rfc8631) | **RT-P05 Subsetting API**: Points to machine-readable service descriptions (OpenAPI, GraphQL). | `Link: </openapi.json>; rel="service-desc"; type="application/vnd.oai.openapi+json"` |
| **`service-doc`** | [RFC 8631](https://www.rfc-editor.org/info/rfc8631) | **RT-P05 Subsetting API**: Points to human-readable API or service documentation. | `Link: </docs>; rel="service-doc"; type="text/html"` |

---

## Configuration Reference

### YAML Test Suite Configuration

Test suites can be configured in YAML targeting specific URLs or URL patterns:

```yaml
version: "1.0"
name: "EOSC RT Conformance Suite"

tests:
  - name: "Dataset Profile & Signposting Conformance"
    targets:
      urls:
        - "https://example.org/dataset/123"
      patterns:
        - "https://example.org/dataset/*"
    expand_linksets: true
    expect:
      relations:
        - rel: "profile"
          target: "https://example.org/profiles/dataset-v1"
          exists: true

        - rel: "describedby"
          type: "application/ld+json"
          min_count: 1

        - rel: "cite-as"
          target_pattern: "^https://doi\\.org/10\\..*"
          exists: true

        - rel: "license"
          exists: true

        - rel: "latest-version"
          exists: true
```

### Environment Variables

| Variable | Description |
| :--- | :--- |
| `TEST_CONFIG_PATH` | Path to a YAML configuration file. |
| `TEST_CONFIG_YAML` | Inline YAML configuration string. |
| `TEST_URLS` | Fallback list of URLs to test for basic profile declaration. |
| `TS_NAME` | Name of the test suite (default: `rt-test`). |

---

## Local Execution & Docker

### Running with Docker Compose

```bash
docker compose up --build
```

The JUnit XML report is written to `./reports/localtestrun_report.xml`.

### Running Unit Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```
