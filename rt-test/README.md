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

`rt-test` supports two complementary ways to define test suites:
1. **High-Level RT Patterns (`patterns:`)**: Declare standard Radical Transparency usage patterns (`PT-01` to `PT-08`) using semantic role-to-URI bindings. The engine automatically expands and validates all required link relations across multiple resources.
2. **Raw Relation Tests (`tests:`)**: Explicitly specify target URLs and granular link relation expectation rules (`rel`, `target`, `type`, `profile`, `min_count`, `exists`, SPARQL).

Both approaches can be used in the same YAML suite or in dedicated files (see [`example_config.yaml`](file:///c:/Users/cedricd/Documents/Github/grmp-test-implementations/rt-test/example_config.yaml) and [`example_config_patterns.yaml`](file:///c:/Users/cedricd/Documents/Github/grmp-test-implementations/rt-test/example_config_patterns.yaml)).

---

### Authoring Test Suites: Patterns vs. Raw Tests

#### 1. Profile Conformity Declaration (PT-01 / RT-P01)

Declare and verify that a resource conforms to a specific profile, and optionally verify the profile's description and type.

* **Pattern Syntax (Recommended)**:
  ```yaml
  patterns:
    - name: "ARMS Marine Genomic Profile Conformance"
      type: "PT-01"
      uris:
        resource: "http://localhost:8080/id/dataset/arms-mbon"
        profile: "http://localhost:8080/id/profile/marine-genomic-dataset-profile"
        profile_description: "http://localhost:8080/id/profile/marine-genomic-dataset-profile.html"
        profile_type: "https://www.rfc-editor.org/info/rfc6906"
  ```

* **Raw Equivalent Syntax**:
  ```yaml
  tests:
    - name: "ARMS Marine Genomic Profile Conformance (Resource)"
      targets:
        urls: ["http://localhost:8080/id/dataset/arms-mbon"]
      expect:
        relations:
          - rel: "profile"
            target: "http://localhost:8080/id/profile/marine-genomic-dataset-profile"
            exists: true

    - name: "ARMS Marine Genomic Profile Conformance (Profile Metadata)"
      targets:
        urls: ["http://localhost:8080/id/profile/marine-genomic-dataset-profile"]
      expect:
        relations:
          - rel: "type"
            target: "https://www.rfc-editor.org/info/rfc6906"
            exists: true
          - rel: "describedby"
            target: "http://localhost:8080/id/profile/marine-genomic-dataset-profile.html"
            exists: true
  ```

---

#### 2. Content Negotiation Menu (PT-03 / RT-P03)

Test representation variants for a conceptual identity resource, ensuring variants advertise alternate formats and restore identity after redirects via `rel="self"`.

* **Pattern Syntax (Recommended)**:
  ```yaml
  patterns:
    - name: "VLIZ Institute Conneg Variants Menu"
      type: "PT-03"
      uris:
        concept: "http://localhost:8080/id/institute/vliz"
        variant_menu: "http://localhost:8080/id/institute/vliz.ls.json"
        variants:
          - uri: "http://localhost:8080/id/institute/vliz.ttl"
            type: "text/turtle"
          - uri: "http://localhost:8080/id/institute/vliz.jsonld"
            type: "application/ld+json"
          - uri: "http://localhost:8080/id/institute/vliz.html"
            type: "text/html"
  ```

* **Raw Equivalent Syntax**:
  ```yaml
  tests:
    # 1. Check conceptual resource advertises alternates & linkset
    - name: "VLIZ Institute Conceptual Resource"
      targets:
        urls: ["http://localhost:8080/id/institute/vliz"]
      expect:
        relations:
          - rel: "alternate"
            target: "http://localhost:8080/id/institute/vliz.ttl"
            type: "text/turtle"
            exists: true
          - rel: "alternate"
            target: "http://localhost:8080/id/institute/vliz.jsonld"
            type: "application/ld+json"
            exists: true
          - rel: "alternate"
            target: "http://localhost:8080/id/institute/vliz.html"
            type: "text/html"
            exists: true
          - rel: "linkset"
            target: "http://localhost:8080/id/institute/vliz.ls.json"
            exists: true

    # 2. Check each variant restores identity anchor via rel=self
    - name: "VLIZ Turtle Variant Self Restoration"
      targets:
        urls: ["http://localhost:8080/id/institute/vliz.ttl"]
      expect:
        relations:
          - rel: "self"
            target: "http://localhost:8080/id/institute/vliz"
            exists: true
          - rel: "linkset"
            target: "http://localhost:8080/id/institute/vliz.ls.json"
            exists: true

    - name: "VLIZ HTML Variant Self Restoration"
      targets:
        urls: ["http://localhost:8080/id/institute/vliz.html"]
      expect:
        relations:
          - rel: "self"
            target: "http://localhost:8080/id/institute/vliz"
            exists: true
  ```

---

#### 3. No Landing Page Solution (PT-04 / RT-P04)

Validate direct payload access without requiring an intermediate HTML landing page, connecting data payloads to PIDs via `rel="cite-as"` and to metadata descriptions via `rel="describedby"`.

* **Pattern Syntax (Recommended)**:
  ```yaml
  patterns:
    - name: "ARMS Genomic Data Direct CSV Payload"
      type: "PT-04"
      uris:
        pid: "http://localhost:8080/doi/10.14284/578"
        content: "http://localhost:8080/data/arms-mbon-18s.csv"
        descriptions:
          - uri: "http://localhost:8080/id/dataset/arms-mbon.html"
            type: "text/html"
          - uri: "http://localhost:8080/id/dataset/arms-mbon.ttl"
            type: "text/turtle"
  ```

* **Raw Equivalent Syntax**:
  ```yaml
  tests:
    - name: "Direct CSV Data Payload Citation & Descriptions"
      targets:
        urls: ["http://localhost:8080/data/arms-mbon-18s.csv"]
      expect:
        relations:
          - rel: "cite-as"
            target: "http://localhost:8080/doi/10.14284/578"
            exists: true
          - rel: "describedby"
            target: "http://localhost:8080/id/dataset/arms-mbon.html"
            type: "text/html"
            exists: true
          - rel: "describedby"
            target: "http://localhost:8080/id/dataset/arms-mbon.ttl"
            type: "text/turtle"
            exists: true

    - name: "Metadata Description Describes PID"
      targets:
        urls: ["http://localhost:8080/id/dataset/arms-mbon.ttl"]
      expect:
        relations:
          - rel: "describes"
            target: "http://localhost:8080/doi/10.14284/578"
            exists: true
  ```

---

#### 4. Subsetting API & Dynamic Services (PT-05 / RT-P05)

* **Pattern Syntax (Recommended)**:
  ```yaml
  patterns:
    - name: "Marine Observation API"
      type: "PT-05"
      uris:
        dataset: "http://localhost:8080/id/dataset/arms-mbon"
        base_api: "http://localhost:8080/id/service/marineinfo-api"
        fragment_api: "http://localhost:8080/api/observations/v1?taxon=123"
        api_catalog: "http://localhost:8080/.well-known/api-catalog"
        service_desc: "http://localhost:8080/api/openapi.json"
        service_doc: "http://localhost:8080/api/docs/"
  ```

* **Raw Equivalent Syntax**:
  ```yaml
  tests:
    - name: "Base API Metadata & Composition"
      targets:
        urls: ["http://localhost:8080/id/service/marineinfo-api"]
      expect:
        relations:
          - rel: "cite-as"
            target: "http://localhost:8080/id/dataset/arms-mbon"
            exists: true
          - rel: "item"
            target: "http://localhost:8080/api/observations/v1?taxon=123"
            exists: true
          - rel: "api-catalog"
            target: "http://localhost:8080/.well-known/api-catalog"
            exists: true
          - rel: "service-desc"
            target: "http://localhost:8080/api/openapi.json"
            exists: true

    - name: "Fragment API Collection & Citation"
      targets:
        urls: ["http://localhost:8080/api/observations/v1?taxon=123"]
      expect:
        relations:
          - rel: "collection"
            target: "http://localhost:8080/id/service/marineinfo-api"
            exists: true
          - rel: "cite-as"
            target: "http://localhost:8080/id/dataset/arms-mbon"
            exists: true
  ```

---

### RT Patterns Quick Reference (PT-01 to PT-08)

| Pattern ID | Name | Required URI Roles | Optional URI Roles |
| :--- | :--- | :--- | :--- |
| **`PT-01`** | **Profile Conformity Declaration** | `resource`, `profile` | `profile_description`, `profile_type` |
| **`PT-02`** | **Profile Composition** | `resource`, `composite_profile`, `member_profiles` (list) | `check_composite` |
| **`PT-03`** | **Content Negotiation Menu** | `concept` (or `self`), `variants` (list) | `variant_menu`, `check_variants` |
| **`PT-04`** | **No Landing Page Solution** | `pid`, `content` | `descriptions` (list), `check_descriptions` |
| **`PT-05`** | **Subsetting API** | `dataset`, `base_api` | `fragment_api`, `api_catalog`, `service_desc`, `service_doc`, `service_meta`, `status` |
| **`PT-06`** | **Hostwide Discovery** | `host` | `robots_txt`, `sitemap`, `resources` (list) |
| **`PT-07`** | **Catalog Assistance** | `api_catalog` | `api_catalog_sitemap`, `sitemap_index`, `api_endpoints` (list), `resources` (list) |
| **`PT-08`** | **Large Linksets Split-up** | `resource`, `master_linkset`, `child_linksets` (list) | `check_children` |


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

You can execute conformance tests using Docker Compose against either the fully compliant reference server (Port 8080) or the simulated gapped server (Port 8081).

#### 1. Reference Implementation Test Suite (Port 8080 — 100% Compliant)

Runs the conformance test suite using [`example_config.yaml`](file:///c:/Users/cedricd/Documents/Github/grmp-test-implementations/rt-test/example_config.yaml) targeting `http://localhost:8080`:

```bash
docker compose up --build
```
*or explicitly specifying the file:*
```bash
docker compose -f docker-compose.yml up --build
```

The JUnit XML report is written to `./reports/localtestrun_report.xml`.

#### 2. Gapped / Defective Repository Test Suite (Port 8081 — Expected Defects)

Runs the test suite using [`example_config.bad.yaml`](file:///c:/Users/cedricd/Documents/Github/grmp-test-implementations/rt-test/example_config.bad.yaml) targeting `http://localhost:8081` to verify detection of missing link relations, absent profiles, unanchored payloads, and sitemap/linkset gaps:

```bash
docker compose -f docker-compose.bad.yaml up --build
```

The JUnit XML report is written to `./reports/gappedtestrun_report.xml`.

---

### Running Locally with Python CLI

```bash
# Run against reference server (Port 8080)
python src/rt_test.py -c example_config.yaml

# Run against gapped server (Port 8081)
python src/rt_test.py -c example_config.bad.yaml
```

### Running Unit Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

