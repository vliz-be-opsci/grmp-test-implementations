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

### Authoring Test Suites: Radical Transparency Patterns (PT-01 to PT-08)

The test suite provides built-in support for all 8 Radical Transparency patterns defined in the [EOSC Linkset Usage Patterns](https://github.com/eosc-semantic-interop/if-solutions-proposals/tree/main/proposals/radical-transparency/linkset-usage-patterns).

Each pattern below details:
1. **Required HTTP Link Relationships**: What headers/linksets each endpoint must serve.
2. **Test Output ASCII Diagram**: The structured diagram rendered by `rt-test` during execution.
3. **Configurable URIs & Roles**: The parameter schema to provide in YAML.
4. **YAML Example**: Drop-in test configuration.

---

#### 1. Profile Conformity Declaration (PT-01 / RT-P01)

Declares that a resource conforms to a specific functional profile ([RFC 6906](https://www.rfc-editor.org/info/rfc6906)), and optionally verifies profile metadata (`rel="describedby"`), profile type declaration (`rel="type"`), and profile description document type/conformance (`rel="type"` on the description document).

* **Required HTTP Link Relationships**:
  - `GET <resource>` $\rightarrow$ `Link: <<profile>>; rel="profile"`
  - `GET <profile>` $\rightarrow$ `Link: <<profile_description>>; rel="describedby"`, `Link: <<profile_type>>; rel="type"`
  - `GET <profile_description>` $\rightarrow$ `Link: <<profile_description_type>>; rel="type"` (optional)

* **Test Output ASCII Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: Profile Conformity Declaration (PT-01)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Resource: <resource>                                                       |
  +----------------------------------------------------------------------------+
          |
          | rel="profile" [✓ PASS]
          v
  +----------------------------------------------------------------------------+
  | Profile: <profile>                                                         |
  +----------------------------------------------------------------------------+
          |
          +---> rel="describedby" -> <profile_description>             [✓ PASS]
          |     +--- rel="type"   -> <profile_description_type>        [✓ PASS]
          +---> rel="type"        -> <profile_type>                    [✓ PASS]
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `resource` | URI string | **Required** | The target dataset, service, or landing page declaring conformance. |
  | `profile` | URI string | **Required** | The canonical profile URI that the resource conforms to. |
  | `profile_description` | URI string or object | Optional | Documentation or schema describing the profile via `rel="describedby"`. Supports string URI or object with `uri` and `type`. |
  | `profile_description_type` | URI string | Optional | Type standard URI for the profile description document (e.g. `http://www.w3.org/ns/dx/prof/Profile`). |
  | `profile_type` | URI string | Optional | Profile type identifier via `rel="type"` (e.g. `https://www.rfc-editor.org/info/rfc6906` or `http://www.w3.org/ns/dx/prof/Profile`). |
  | `profile_alternate` | URI string / list | Optional | Alternate representation URI(s) for the profile (e.g. `.ttl`, `.jsonld`, `.html`). |

* **YAML Pattern Syntax**:
  ```yaml
  patterns:
    - name: "ARMS Marine Genomic Profile Conformance"
      type: "PT-01"
      uris:
        resource: "http://localhost:8080/id/dataset/arms-mbon"
        profile: "http://localhost:8080/id/profile/marine-genomic-dataset-profile"
        profile_description: "http://localhost:8080/id/profile/marine-genomic-dataset-profile.ttl"
        profile_description_type: "http://www.w3.org/ns/dx/prof/Profile"
        profile_type: "http://www.w3.org/ns/dx/prof/Profile"
  ```

---

#### 2. Profile Composition (PT-02 / RT-P02)

Validates hierarchical or composite profiles where a root profile declares member sub-profiles using `rel="http://schema.org/hasPart"`.

* **Required HTTP Link Relationships**:
  - `GET <resource>` $\rightarrow$ `Link: <<composite_profile>>; rel="profile"`
  - `GET <composite_profile>` $\rightarrow$ `Link: <<member_profile_N>>; rel="http://schema.org/hasPart"`

* **Test Output ASCII Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: Profile Composition (PT-02)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Resource: <resource>                                                       |
  +----------------------------------------------------------------------------+
          |
          | rel="profile" [✓ PASS]
          v
  +----------------------------------------------------------------------------+
  | Composite Profile: <composite_profile>                                     |
  +----------------------------------------------------------------------------+
          |
          | Member Profiles (rel="http://schema.org/hasPart"):
          +---> <member_profile_1> [✓ PASS]
          +---> <member_profile_2> [✓ PASS]
          +---> <member_profile_3> [✓ PASS]
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `resource` | URI string | **Required** | Target resource referencing the composite profile. |
  | `composite_profile` | URI string | **Required** | Root composite profile aggregating member specifications. |
  | `member_profiles` | List of URIs / Objects | **Required** | List of child member sub-profiles composed inside the root profile. |
  | `check_composite` | Boolean | Optional | Harvest and validate member links directly on the composite profile (default: `true`). |

* **YAML Pattern Syntax**:
  ```yaml
  patterns:
    - name: "Marine Genomic Profile Composition"
      type: "PT-02"
      uris:
        resource: "http://localhost:8080/id/dataset/arms-mbon"
        composite_profile: "http://localhost:8080/id/profile/marine-genomic-dataset-profile"
        member_profiles:
          - "http://localhost:8080/id/profile/schema-dataset-profile"
          - "http://localhost:8080/id/profile/dcat3-dataset-profile"
          - "http://localhost:8080/id/profile/ro-crate-package-profile"
  ```

---

#### 3. Content Negotiation Menu & Variant Self-Restoration (PT-03 / RT-P03)

Validates representation variants for a conceptual identity resource, checking that each variant advertises alternate media types via `rel="alternate"` and restores conceptual identity after HTTP 303 redirects via `rel="self"`.

* **Required HTTP Link Relationships**:
  - `GET <concept>` $\rightarrow$ `Link: <<variant_menu>>; rel="linkset"`, `Link: <<variant_N>>; rel="alternate"; type="<mime>"`
  - `GET <variant_N>` $\rightarrow$ `Link: <<concept>>; rel="self"` (restoring canonical identity anchor)

* **Test Output ASCII Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: Content Negotiation Menu (PT-03)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Concept Identity: <concept>                                                |
  +----------------------------------------------------------------------------+
          |
          +--- rel="linkset" -> <variant_menu> [✓ PASS]
          |
          | Representation Variants (rel="alternate"):
          +---> <variant_1> [<type_1>] [✓ PASS] -> self [<concept>] [✓ PASS]
          +---> <variant_2> [<type_2>] [✓ PASS] -> self [<concept>] [✓ PASS]
          +---> <variant_3> [<type_3>] [✓ PASS] -> self [<concept>] [✓ PASS]
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `concept` | URI string | **Required** | The conceptual/abstract resource identity URI (or `self`). |
  | `variants` | List of Objects / URIs | **Required** | List of format variants (`uri`, optional `type`, optional `profile`). |
  | `variant_menu` | URI string | Optional | Standalone linkset document aggregating representation variants. |
  | `check_variants` | Boolean | Optional | Harvest variants and assert `rel="self"` identity restoration (default: `true`). |

* **YAML Pattern Syntax**:
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

---

#### 4. No Landing Page Solution (PT-04 / RT-P04)

Validates direct payload access (CSV, NetCDF, GeoTIFF, PDF) without requiring an intermediate HTML landing page. Connects raw payloads directly to PIDs via `rel="cite-as"` and metadata descriptions via `rel="describedby"`, verifying that metadata descriptions link back to the conceptual dataset/resource URI via `rel="describes"` and link across sibling metadata formats via `rel="alternate"`.

* **Required HTTP Link Relationships**:
  - `GET <content>` $\rightarrow$ `Link: <<pid>>; rel="cite-as"`, `Link: <<description_N>>; rel="describedby"; type="<mime>"`
  - `GET <description_N>` $\rightarrow$ `Link: <<resource>>; rel="describes"`, `Link: <<other_description>>; rel="alternate"; type="<mime>"`

* **Test Output ASCII Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: No Landing Page Solution (PT-04)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Content Payload: <content>                                                 |
  +----------------------------------------------------------------------------+
          |                                    |
          | rel="cite-as" [✓ PASS]             | rel="describedby"
          v                                    v
    [ PID / Handle ]                 [ Metadata Descriptions ]
    <pid>                            * <description_1> [<type_1>] [✓ PASS] (describes resource [✓ PASS])
                                     * <description_2> [<type_2>] [✓ PASS] (describes resource [✓ PASS])
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `pid` | URI string | **Required** | Permanent citation identifier (DOI, Handle, URN) referenced via `rel="cite-as"`. |
  | `content` | URI string | **Required** | Downloadable data payload URL. |
  | `resource` | URI string | Optional | Conceptual dataset or entity URI described by metadata descriptions (or `dataset`). |
  | `descriptions` | List of Objects / URIs | Optional | Metadata description documents (`uri`, optional `type`, optional `profile`). |
  | `check_descriptions` | Boolean | Optional | Harvest descriptions to verify `rel="describes"` points back to resource (default: `true`). |

* **YAML Pattern Syntax**:
  ```yaml
  patterns:
    - name: "Direct Dataset Payload Access"
      type: "PT-04"
      uris:
        pid: "https://doi.org/10.14284/170"
        content: "http://localhost:8080/data/archive-170.zip"
        resource: "http://localhost:8080/id/dataset/170"
        descriptions:
          - uri: "http://localhost:8080/id/dataset/170.ttl"
            type: "text/turtle"
          - uri: "http://localhost:8080/id/dataset/170.html"
            type: "text/html"
  ```

---

#### 5. Subsetting & Dynamic Query APIs (PT-05 / RT-P05)

Validates dynamic subsetting APIs and query fragment endpoints, linking query responses to the base API service (`rel="collection"`), the master dataset PID (`rel="cite-as"`), API catalogs (`rel="api-catalog"`), and OpenAPI descriptors (`rel="service-desc"`).

* **Required HTTP Link Relationships**:
  - `GET <base_api>` $\rightarrow$ `Link: <<dataset>>; rel="cite-as"`, `Link: <<fragment_api>>; rel="item"`, `Link: <<api_catalog>>; rel="api-catalog"`, `Link: <<service_desc>>; rel="service-desc"`
  - `GET <fragment_api>` $\rightarrow$ `Link: <<base_api>>; rel="collection"`, `Link: <<dataset>>; rel="cite-as"`

* **Test Output ASCII Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: Subsetting API & Dynamic Services (PT-05)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Base API: <base_api>                                                       |
  +----------------------------------------------------------------------------+
          |                                    |
          | rel="cite-as" [✓ PASS]             | rel="item" [✓ PASS]
          v                                    v
    [ Dataset PID ]                    [ Fragment API ]
    <dataset>                          <fragment_api>
                                               |
                                               +--- rel="collection" -> <base_api> [✓ PASS]
                                               +--- rel="cite-as" -> <dataset> [✓ PASS]
          |
          | Service Capabilities & Metadata:
          +--- rel="api-catalog"  -> <api_catalog>  [✓ PASS]
          +--- rel="service-desc" -> <service_desc> [✓ PASS]
          +--- rel="service-doc"  -> <service_doc>  [✓ PASS]
          +--- rel="status"       -> <status>       [✓ PASS]
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `dataset` | URI string | **Required** | Underlying dataset PID / DOI. |
  | `base_api` | URI string | **Required** | Main API service root endpoint. |
  | `fragment_api` | URI string | Optional | Subsetting or parameterized query endpoint. |
  | `api_catalog` | URI string | Optional | Registry / catalog endpoint (`/.well-known/api-catalog`). |
  | `service_desc` | URI string | Optional | Machine-readable API definition (OpenAPI / Swagger). |
  | `service_doc` | URI string | Optional | Human documentation URL. |
  | `status` | URI string | Optional | Health and uptime endpoint. |

* **YAML Pattern Syntax**:
  ```yaml
  patterns:
    - name: "WoRMS Aphia Subsetting Service"
      type: "PT-05"
      uris:
        dataset: "https://doi.org/10.14284/170"
        base_api: "http://localhost:8080/rest/"
        fragment_api: "http://localhost:8080/rest/AphiaRecordsByVernacular/crab?offset=1"
        api_catalog: "http://localhost:8080/.well-known/api-catalog"
        service_desc: "http://localhost:8080/rest/api-docs/openapi.yaml"
        service_doc: "http://localhost:8080/rest/docs"
        status: "http://localhost:8080/rest/health"
  ```

---

#### 6. Hostwide Crawler Discovery (PT-06 / RT-P06)

Validates automated hostwide discovery starting from `/robots.txt` $\rightarrow$ primary `sitemap.xml` (with `<rs:ln>` / `<xhtml:link>` signposting annotations) $\rightarrow$ discoverable resources, plus cross-reference consistency checks across the sitemap, the resource itself, and referenced linksets.

* **Required HTTP Link Relationships & Consistency Checks**:
  - `GET <robots_txt>` $\rightarrow$ contains `Sitemap: <sitemap>` (optional if `robots_txt: false`)
  - `GET <sitemap>` $\rightarrow$ contains `<loc>` references to `<resource_N>`
  - If a resource defines a `linkset` or `alternates`:
    - **In Sitemap**: `<rs:ln rel="linkset">` and `<rs:ln rel="alternate">` match under the resource `<url>` block.
    - **On Resource**: HTTP `Link` headers or body links declare the same `rel="linkset"` and `rel="alternate"` targets.
    - **In Linkset Document**: The referenced linkset (`application/linkset+json`) binds the same `rel="alternate"` targets under `anchor="<resource_URI>"`.

* **Test Output ASCII Diagrams**:
  1. **Hostwide Discovery Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: Hostwide Crawler Discovery (PT-06)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Host: <host>                                                               |
  +----------------------------------------------------------------------------+
          |
          v
    [ robots.txt: <host>/robots.txt ]
          | Sitemap directive [✓ PASS]
          v
    [ sitemap.xml: <sitemap> ]
          | Resource links:
          +---> <resource_1>                                            [✓ PASS]
          |     +--- linkset: <resource_1.linkset.json>                 [✓ PASS]
          |     +--- alternate: <resource_1.ttl>                        [✓ PASS]
          |     +--- profile: <resource_profile>                        [✓ PASS]
          +---> <resource_2>                                            [✓ PASS]
  ==============================================================================
  ```

  2. **Alternate Resources & Triangulation Diagram**:
  Rendered for each resource and linkset consistency check, displaying the relations from each discovery perspective (sitemap `<rs:ln>`, resource headers, and RFC 9264 linkset document) plus a cross-reference triangulation matrix:
  ```text
  ==============================================================================
  DIAGRAM: Resource Linkset [<ls_uri>] Alternate Consistency
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Alternate Resources & Consistency Analysis: <resource_uri>                  |
  +----------------------------------------------------------------------------+
    Target Resource:   <resource_uri>
    Linkset Document:  <ls_uri>
    Sitemap XML:       <sitemap_uri>

  [1] Sitemap Perspective (<sitemap_uri>):
        +--- <loc> entry: <resource_uri>                                [✓ PASS]
        +--- rel="linkset"   -> <ls_uri>                                [✓ PASS]
        +--- rel="alternate" -> <alt_1>                                 [✓ PASS]
        +--- rel="profile"   -> <profile_uri>                           [✓ PASS]

  [2] Resource Headers Perspective (GET <resource_uri>):
        +--- HTTP Status 200: <resource_uri>                            [✓ PASS]
        +--- rel="linkset"   -> <ls_uri>                                [✓ PASS]
        +--- rel="alternate" -> <alt_1>                                 [✓ PASS]
        +--- rel="profile"   -> <profile_uri>                           [✓ PASS]

  [3] Linkset Perspective (GET <ls_uri> with anchor=<resource_uri>):
        +--- HTTP Status 200: <ls_uri>                                  [✓ PASS]
        +--- rel="alternate" -> <alt_1>                                 [✓ PASS]
        +--- rel="profile"   -> <profile_uri>                           [✓ PASS]

  ------------------------------------------------------------------------------
  Consistency Triangulation Matrix:
  Target Relation / URI         |   Sitemap    |   Resource   |   Linkset    |   Consistency  
  ------------------------------------------------------------------------------
  linkset   -> <ls_uri>         |   [✓ PASS]   |   [✓ PASS]   |     N/A      |   [✓ IN SYNC]  
  alternate -> <alt_1>          |   [✓ PASS]   |   [✓ PASS]   |   [✓ PASS]   |   [✓ IN SYNC]  
  profile   -> <profile_uri>    |   [✓ PASS]   |   [✓ PASS]   |   [✓ PASS]   |   [✓ IN SYNC]  
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `host` | URI string | **Required** | Base origin URL of the host (e.g. `http://localhost:8080`). |
  | `robots_txt` | Boolean or URI string | Optional | Defaults to `true` (checks `<host>/robots.txt`). Set to `false` to skip, or provide a custom URL. |
  | `sitemap` | URI string | Optional | Target `sitemap.xml` URL advertised in `robots.txt`. |
  | `resources` | List of URIs / Objects | Optional | Key resources expected in `<loc>`. Supports plain URIs or indented objects with `uri`, `linkset`, `alternates`, and `profile`. |

* **YAML Pattern Syntax**:
  ```yaml
  patterns:
    - name: "Hostwide Crawler Discovery"
      type: "PT-06"
      uris:
        host: "http://localhost:8080"
        robots_txt: true
        sitemap: "http://localhost:8080/sitemap.xml"
        resources:
          - uri: "http://localhost:8080/id/dataset/arms-mbon"
            linkset: "http://localhost:8080/id/dataset/arms-mbon.linkset.json"
            alternates:
              - "http://localhost:8080/id/dataset/arms-mbon.ttl"
              - "http://localhost:8080/id/dataset/arms-mbon.jsonld"
            profile: "http://localhost:8080/id/profile/marine-genomic-dataset-profile"
          - uri: "http://localhost:8080/id/dataset/arms-2018"
            profile: "http://localhost:8080/id/profile/marine-ecological-baseline-profile"
          - "http://localhost:8080/id/dataset/north-sea-sensors"
  ```

---

#### 7. Catalog Assistance for Hostwide Discovery (PT-07 / RT-P07)

Implements the [Catalogue Assisted Resource Exposure](https://github.com/eosc-semantic-interop/if-solutions-proposals/blob/main/proposals/radical-transparency/linkset-usage-patterns/07-catalog-assistance.svg) pattern, delegating granular digital asset discovery to specialized API catalogs and sitemap hierarchies without overwhelming static sitemaps.

* **Required HTTP & Sitemap Relationships (Tripartite Architecture)**:
  - **Sitemaps Hierarchy (`sitemaps.org`)**:
    - `GET <host>/robots.txt` $\rightarrow$ `Sitemap: <<sitemap_index>>`
    - `GET <sitemap_index>` (Root Sitemap Index) $\rightarrow$ `<sitemap><loc><<api_catalog_sitemap>></loc></sitemap>`, `<sitemap><loc><<api_sub_sitemap>></loc></sitemap>`
    - `GET <api_catalog_sitemap>` $\rightarrow$ `Link: <<api_catalog>>; rel="self"`, `<url><loc><<api_endpoint>></loc></url>`
    - `GET <api_sub_sitemap>` $\rightarrow$ `Link: <<api_endpoint>>; rel="self"`, `<url><loc><<subresource>></loc></url>`
  - **API Catalog (`api-catalog`)**:
    - `GET <api_catalog>` ([RFC 9727](https://www.rfc-editor.org/info/rfc9727) `/.well-known/api-catalog`) $\rightarrow$ `Link: <<api_catalog_sitemap>>; rel="alternate"`, `Link: <<api_endpoint>>; rel="item"`
  - **API Services & Subresources (`api & subresources`)**:
    - `GET <api_endpoint>` $\rightarrow$ `Link: <<api_catalog>>; rel="api-catalog"`, `Link: <<api_sub_sitemap>>; rel="alternate"`, (optional `Link: <<profile>>; rel="profile"`)
    - `GET <subresource>` $\rightarrow$ `Link: <<api_endpoint>>; rel="collection"`

* **Test Output ASCII Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: Catalog Assistance for Hostwide Discovery (PT-07)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Host: <host>                                                               |
  +----------------------------------------------------------------------------+
          |
          v [ robots.txt: <host>/robots.txt ]
          | Sitemap index directive                                    [✓ PASS]
          v
  +----------------------------------------------------------------------------+
  | [2] Sitemaps Hierarchy (sitemaps.org)                                      |
  | Root Index: <sitemap_index>                                                |
  +----------------------------------------------------------------------------+
          | Delegated Sitemaps:
          +---> Catalog Sitemap: <api_catalog_sitemap>                 [✓ PASS]
          |     +--- rel="self" -> <api_catalog>                       [✓ PASS]
          |     +--- <loc> item -> <api_endpoint>                      [✓ PASS]
          \---> API Sitemap:     <api_sub_sitemap>                     [✓ PASS]
                +--- rel="self" -> <api_endpoint>                      [✓ PASS]
                +--- <loc> item -> <subresource_1>                     [✓ PASS]

  +----------------------------------------------------------------------------+
  | [3] API Catalog (RFC 9727)                                                 |
  +----------------------------------------------------------------------------+
          +---> rel="alternate" -> <api_catalog_sitemap>               [✓ PASS]
          +---> rel="item"      -> <api_endpoint>                      [✓ PASS]

  +----------------------------------------------------------------------------+
  | [1] API Services & Subresources                                            |
  +----------------------------------------------------------------------------+
          +---> API Endpoint: <api_endpoint>                           [✓ PASS]
                +--- rel="api-catalog" -> <api_catalog>                [✓ PASS]
                +--- rel="alternate"   -> <api_sub_sitemap>            [✓ PASS]
                +--- Subresources (rel="collection" uplink):
                     +--- <subresource_1>                              [✓ PASS]
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `api_catalog` | URI string | **Required** | RFC 9727 API catalog endpoint (`/.well-known/api-catalog`). |
  | `host` | URI string | Optional | Root host domain (auto-derived from `api_catalog` if omitted). |
  | `robots_txt` | Boolean or URI string | Optional | Defaults to `true` (resolves to `<host>/robots.txt`). Set to `false` to skip. |
  | `sitemap_index` | URI string | Optional | Root sitemap index XML URL advertised in `robots.txt`. |
  | `api_catalog_sitemap` | URI string | Optional | Dedicated catalog sitemap (defaults to `/.well-known/api-catalog/sitemap-index.xml`). |
  | `api_endpoints` | List of Objects / URIs | Optional | API endpoints supporting `uri`, `sitemap`, `profile`, and `subresources`. |
  | `resources` | List of URIs | Optional | Legacy alias for granular subresources. |

* **YAML Pattern Syntax**:
  ```yaml
  patterns:
    - name: "Hostwide API Catalog & Feeds"
      type: "PT-07"
      uris:
        host: "http://localhost:8080"
        robots_txt: true
        sitemap_index: "http://localhost:8080/sitemap-index.xml"
        api_catalog: "http://localhost:8080/.well-known/api-catalog"
        api_catalog_sitemap: "http://localhost:8080/.well-known/api-catalog/sitemap-index.xml"
        api_endpoints:
          - uri: "http://localhost:8080/api/observations/v1"
            sitemap: "http://localhost:8080/api/observations/v1/sitemap.xml"
            profile: "https://w3id.org/ldes/specification"
            subresources:
              - "http://localhost:8080/api/observations/v1/fragments/1"
  ```

---

#### 8. Large Linksets Split-Up (PT-08 / RT-P08)

Validates large linkset partitioning according to [RFC 9264](https://www.rfc-editor.org/info/rfc9264), verifying that a master linkset links to segmented child linksets via `rel="item"` and child linksets link back via `rel="collection"`.

* **Required HTTP Link Relationships**:
  - `GET <resource>` $\rightarrow$ `Link: <<master_linkset>>; rel="linkset"; type="application/linkset+json"`
  - `GET <master_linkset>` $\rightarrow$ `Link: <<child_linkset_N>>; rel="item"`
  - `GET <child_linkset_N>` $\rightarrow$ `Link: <<master_linkset>>; rel="collection"`

* **Test Output ASCII Diagram**:
  ```text
  ==============================================================================
  DIAGRAM: Large Linkset Hierarchy (PT-08)
  Overall Status: [✓ PASS]
  ------------------------------------------------------------------------------
  +----------------------------------------------------------------------------+
  | Resource: <resource>                                                       |
  +----------------------------------------------------------------------------+
          |
          | rel="linkset" [✓ PASS]
          v
  +----------------------------------------------------------------------------+
  | Master Linkset: <master_linkset>                                           |
  +----------------------------------------------------------------------------+
          | Child Linksets:
          +---> <child_linkset_1> [✓ PASS] (rel="collection" -> <master_linkset> [✓ PASS])
          +---> <child_linkset_2> [✓ PASS] (rel="collection" -> <master_linkset> [✓ PASS])
          +---> <child_linkset_3> [✓ PASS] (rel="collection" -> <master_linkset> [✓ PASS])
  ==============================================================================
  ```

* **Configurable URIs & Roles (`uris:`)**:
  | URI Role | Type | Status | Description |
  | :--- | :--- | :--- | :--- |
  | `resource` | URI string | **Required** | Primary resource referencing the master linkset document. |
  | `master_linkset` | URI string | **Required** | Root master linkset document URL (`application/linkset+json`). |
  | `child_linksets` | List of URIs / Objects | **Required** | Child segmented linksets (e.g. profiles, variants, services linksets). |
  | `check_children` | Boolean | Optional | Harvest and validate `rel="collection"` on each child linkset (default: `true`). |

* **YAML Pattern Syntax**:
  ```yaml
  patterns:
    - name: "VLIZ Large Linkset Hierarchy"
      type: "PT-08"
      uris:
        resource: "http://localhost:8080/id/institute/vliz"
        master_linkset: "http://localhost:8080/id/institute/vliz.ls.json"
        child_linksets:
          - "http://localhost:8080/id/institute/vliz-profiles.ls.json"
          - "http://localhost:8080/id/institute/vliz-variants.ls.json"
          - "http://localhost:8080/id/institute/vliz-services.ls.json"
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
| `RT_DIAGRAMS` | Control ASCII pattern diagram rendering (`always`, `on-failure`, `never`). Default: `on-failure`. |

---

### Command Line Options

| Option | Flag | Description | Default |
| :--- | :--- | :--- | :--- |
| `--config` | `-c` | Path to test configuration YAML. | `None` / `TEST_CONFIG_PATH` |
| `--report` | `-r` | Path to JUnit XML report output. | `./reports/{TS_NAME}_report.xml` |
| `--urls` | `-u` | Ad-hoc target URLs to harvest and test. | `None` |
| `--expect-rel` | | Expected link relations for ad-hoc URLs. | `profile` |
| `--diagrams` | | When to print ASCII pattern & provenance diagrams (`always`, `on-failure`, `never`). | `on-failure` |

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

