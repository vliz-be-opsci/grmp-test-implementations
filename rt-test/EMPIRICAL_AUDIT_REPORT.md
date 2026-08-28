# Radical Transparency (RT) Empirical Conformance Reference Report

This document specifies **every resource, HTTP response header, `curl -I` invocation, RFC 9264 JSON linkset, XML sitemap entry, and link relation** required for **100% of test cases to pass** in the [`config_localhost_empirical.yaml`](./config_localhost_empirical.yaml) test suite across **Radical Transparency Patterns PT-01 through PT-08**.

---

## 1. Global Resource-Type Pattern Adherence Matrix

Every digital asset in the ecosystem fulfills specific roles governed by RFC specifications (RFC 6906, RFC 6573, RFC 9264, RFC 9727, Signposting / ResourceSync, schema.org).

| Resource Type | Archetypal Examples | Applicable Patterns | Mandatory Link Relations | Expected Carrier Mechanisms |
| :--- | :--- | :--- | :--- | :--- |
| **Conceptual Entity / Dataset Identifier** | `/id/dataset/arms-mbon`<br>`/id/institute/vliz`<br>`/id/project/maregraph` | **PT-01**, **PT-02**, **PT-03**, **PT-06**, **PT-08** | `rel="profile"`<br>`rel="alternate"`<br>`rel="linkset"` | HTTP `Link` headers, HTML `<link>`, Signposting sitemap `<rs:ln>` |
| **Representation Variant** | `/id/dataset/arms-mbon.ttl`<br>`/id/institute/vliz.jsonld`<br>`/id/project/maregraph.html` | **PT-03**, **PT-04** | `rel="self"` (points back to concept)<br>`rel="linkset"`<br>`rel="describes"` (if metadata payload) | HTTP `Link` header, HTML `<link>` (for HTML variants) |
| **Direct Data Payload / Digital Asset** | `/data/arms-mbon-18s.csv`<br>`/data/arms-2018-samples.csv`<br>`/data/ro-crate-paper.pdf` | **PT-04** | `rel="cite-as"` (points to PID/DOI)<br>`rel="describedby"` (points to metadata docs) | HTTP `Link` headers on payload download |
| **Profile & Conformance Standard** | `/id/profile/marine-genomic-dataset-profile`<br>`/id/profile/marine-ecological-baseline-profile` | **PT-01**, **PT-02** | `rel="type"` (e.g. `prof:Profile`)<br>`rel="describedby"`<br>`http://schema.org/hasPart` (for composite profiles) | HTTP `Link` headers, RDF Turtle / JSON-LD triples |
| **Service Gateway / Base API** | `/api/observations/v1` | **PT-05**, **PT-07** | `rel="cite-as"` (dataset)<br>`rel="api-catalog"`<br>`rel="service-desc"` (OpenAPI)<br>`rel="service-doc"`<br>`rel="service-meta"` | HTTP `Link` headers, RFC 9727 API Catalog registration |
| **Discovery Roots & Registries** | `/.well-known/api-catalog`<br>`/robots.txt`<br>`/sitemap.xml`<br>`/sitemap-catalog.xml` | **PT-06**, **PT-07** | `rel="alternate"` (to sitemaps)<br>`rel="item"` (to API endpoints)<br>`rel="self"` | `robots.txt` directives, XML sitemaps, RFC 9727 JSON |
| **Master & Fragment Linksets** | `/id/dataset/arms-mbon.linkset.json`<br>`/id/dataset/arms-mbon.conneg.linkset.json` | **PT-03**, **PT-08** | `rel="item"` (master $\rightarrow$ children)<br>`rel="collection"` (children $\rightarrow$ master) | RFC 9264 `application/linkset+json` |

---

## 2. Hostwide Discovery Artifacts (PT-06 & PT-07)

### 2.1 `/robots.txt`
* **URL:** `http://localhost:8080/robots.txt`  
* **Content-Type:** `text/plain`

```txt
# http://localhost:8080/robots.txt
User-agent: *
Allow: /

# Hostwide Discovery entry points (PT-06 & PT-07)
Sitemap: http://localhost:8080/sitemap.xml
Sitemap: http://localhost:8080/sitemap-catalog.xml
```

---

### 2.2 Hostwide Sitemap Index `/sitemap.xml` (PT-06)
* **URL:** `http://localhost:8080/sitemap.xml`  
* **Content-Type:** `application/xml`  
Includes **ResourceSync (`<rs:ln>`)** link annotations declaring profile conformity and variant linksets.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:rs="http://www.openarchives.org/rs/terms/">

  <!-- ARMS-MBON Genomic Dataset -->
  <url>
    <loc>http://localhost:8080/id/dataset/arms-mbon</loc>
    <lastmod>2026-08-28T00:00:00Z</lastmod>
    <rs:ln rel="profile" href="http://localhost:8080/id/profile/marine-genomic-dataset-profile" />
    <rs:ln rel="linkset" href="http://localhost:8080/id/dataset/arms-mbon.linkset.json" />
  </url>

  <!-- ARMS-2018 Ecological Dataset -->
  <url>
    <loc>http://localhost:8080/id/dataset/arms-2018</loc>
    <lastmod>2026-08-28T00:00:00Z</lastmod>
    <rs:ln rel="profile" href="http://localhost:8080/id/profile/marine-ecological-baseline-profile" />
  </url>

  <!-- EurOBIS Occurrences Dataset -->
  <url>
    <loc>http://localhost:8080/id/dataset/eurobis-occurrences</loc>
    <lastmod>2026-08-28T00:00:00Z</lastmod>
    <rs:ln rel="profile" href="http://localhost:8080/id/profile/schema-dataset-profile" />
  </url>

  <!-- North Sea Sensors Telemetry Dataset -->
  <url>
    <loc>http://localhost:8080/id/dataset/north-sea-sensors</loc>
    <lastmod>2026-08-28T00:00:00Z</lastmod>
    <rs:ln rel="profile" href="http://localhost:8080/id/profile/marine-buoy-telemetry-profile" />
  </url>

  <!-- VLIZ Institute Entity -->
  <url>
    <loc>http://localhost:8080/id/institute/vliz</loc>
    <lastmod>2026-08-28T00:00:00Z</lastmod>
    <rs:ln rel="linkset" href="http://localhost:8080/id/institute/vliz.linkset.json" />
  </url>

</urlset>
```

---

### 2.3 API Catalog Sitemap `/sitemap-catalog.xml` (PT-07)
* **URL:** `http://localhost:8080/sitemap-catalog.xml`  
* **Content-Type:** `application/xml`  
Serves as the static XML alternate for machine crawlers discovering API endpoints.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:rs="http://www.openarchives.org/rs/terms/">

  <!-- API Catalog Self Reference -->
  <url>
    <loc>http://localhost:8080/.well-known/api-catalog</loc>
    <rs:ln rel="alternate" href="http://localhost:8080/sitemap-catalog.xml" />
  </url>

  <!-- MarineInfo Observations Base API -->
  <url>
    <loc>http://localhost:8080/api/observations/v1</loc>
    <rs:ln rel="api-catalog" href="http://localhost:8080/.well-known/api-catalog" />
    <rs:ln rel="service-desc" href="http://localhost:8080/api/openapi.json" />
  </url>

</urlset>
```

---

## 3. Comprehensive Per-Resource Specification (`curl -I` & Response Headers)

---

### 3.1 Conceptual Dataset: `arms-mbon`
* **Patterns Involved:** **PT-01**, **PT-03**, **PT-05**, **PT-06**, **PT-08**
* **URI:** `http://localhost:8080/id/dataset/arms-mbon`

#### `curl -I` Command:
```bash
curl -I -X GET "http://localhost:8080/id/dataset/arms-mbon"
```

#### HTTP Response Headers:
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Link: <http://localhost:8080/id/profile/marine-genomic-dataset-profile>; rel="profile"
Link: <http://localhost:8080/id/dataset/arms-mbon.ttl>; rel="alternate"; type="text/turtle"
Link: <http://localhost:8080/id/dataset/arms-mbon.jsonld>; rel="alternate"; type="application/ld+json"
Link: <http://localhost:8080/id/dataset/arms-mbon.html>; rel="alternate"; type="text/html"
Link: <http://localhost:8080/id/dataset/arms-mbon.rdf>; rel="alternate"; type="application/rdf+xml"
Link: <http://localhost:8080/id/dataset/arms-mbon.linkset.json>; rel="linkset"; type="application/linkset+json"
```

---

### 3.2 Variants for `arms-mbon` (PT-03 Variant Identity Restoration)
* **URIs:**
  * `http://localhost:8080/id/dataset/arms-mbon.ttl`
  * `http://localhost:8080/id/dataset/arms-mbon.jsonld`
  * `http://localhost:8080/id/dataset/arms-mbon.html`
  * `http://localhost:8080/id/dataset/arms-mbon.rdf`

#### `curl -I` Command (Turtle Variant):
```bash
curl -I -X GET "http://localhost:8080/id/dataset/arms-mbon.ttl"
```

#### HTTP Response Headers:
```http
HTTP/1.1 200 OK
Content-Type: text/turtle; charset=utf-8
Link: <http://localhost:8080/id/dataset/arms-mbon>; rel="self"
Link: <http://localhost:8080/id/dataset/arms-mbon.linkset.json>; rel="linkset"; type="application/linkset+json"
Link: <http://localhost:8080/id/dataset/arms-mbon>; rel="describes"
Link: <http://localhost:8080/id/dataset/arms-mbon.html>; rel="alternate"; type="text/html"
```

*(Identical `rel="self"` and `rel="linkset"` returned on `.jsonld`, `.html`, and `.rdf`).*

---

### 3.3 Profile: `marine-genomic-dataset-profile` (PT-01)
* **URI:** `http://localhost:8080/id/profile/marine-genomic-dataset-profile`

#### `curl -I` Command:
```bash
curl -I -X GET "http://localhost:8080/id/profile/marine-genomic-dataset-profile"
```

#### HTTP Response Headers:
```http
HTTP/1.1 200 OK
Content-Type: text/turtle; charset=utf-8
Link: <http://www.w3.org/ns/dx/prof/Profile>; rel="type"
Link: <http://localhost:8080/id/profile/marine-genomic-dataset-profile.ttl>; rel="describedby"; type="text/turtle"
```

---

### 3.4 Composite Profile & Dataset: `arms-2018` (PT-02)
* **Resource URI:** `http://localhost:8080/id/dataset/arms-2018`
* **Composite Profile URI:** `http://localhost:8080/id/profile/marine-ecological-baseline-profile`

#### `curl -I` on `arms-2018`:
```bash
curl -I -X GET "http://localhost:8080/id/dataset/arms-2018"
```
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Link: <http://localhost:8080/id/profile/marine-ecological-baseline-profile>; rel="profile"
```

#### `curl -I` on Composite Profile:
```bash
curl -I -X GET "http://localhost:8080/id/profile/marine-ecological-baseline-profile"
```
```http
HTTP/1.1 200 OK
Content-Type: text/turtle; charset=utf-8
Link: <http://localhost:8080/id/profile/schema-dataset-profile>; rel="http://schema.org/hasPart"
Link: <http://localhost:8080/id/profile/dcat3-dataset-profile>; rel="http://schema.org/hasPart"
Link: <http://localhost:8080/id/profile/darwin-core-occurrence-profile>; rel="http://schema.org/hasPart"
```

---

### 3.5 Direct Data Payloads & PIDs (PT-04 No Landing Page Solution)

#### Payload 1: ARMS-MBON 18S CSV
* **Content URI:** `http://localhost:8080/data/arms-mbon-18s.csv`
* **PID (DOI):** `http://localhost:8080/doi/10.14284/578`

```bash
curl -I -X GET "http://localhost:8080/data/arms-mbon-18s.csv"
```
```http
HTTP/1.1 200 OK
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="arms-mbon-18s.csv"
Link: <http://localhost:8080/doi/10.14284/578>; rel="cite-as"
Link: <http://localhost:8080/id/dataset/arms-mbon.ttl>; rel="describedby"; type="text/turtle"
Link: <http://localhost:8080/id/dataset/arms-mbon.html>; rel="describedby"; type="text/html"
```

#### Payload 2: ARMS-2018 Samples CSV
* **Content URI:** `http://localhost:8080/data/arms-2018-samples.csv`
* **PID (DOI):** `http://localhost:8080/doi/10.14284/412`

```bash
curl -I -X GET "http://localhost:8080/data/arms-2018-samples.csv"
```
```http
HTTP/1.1 200 OK
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="arms-2018-samples.csv"
Link: <http://localhost:8080/doi/10.14284/412>; rel="cite-as"
Link: <http://localhost:8080/id/dataset/arms-2018.ttl>; rel="describedby"; type="text/turtle"
Link: <http://localhost:8080/id/dataset/arms-2018.html>; rel="describedby"; type="text/html"
```

#### Payload 3: RO-Crate Paper PDF
* **Content URI:** `http://localhost:8080/data/ro-crate-paper.pdf`
* **PID (DOI):** `http://localhost:8080/doi/10.3897/biss.6.94630`
* **Described Resource:** `http://localhost:8080/id/publication/ro-crate-paper`

```bash
curl -I -X GET "http://localhost:8080/data/ro-crate-paper.pdf"
```
```http
HTTP/1.1 200 OK
Content-Type: application/pdf
Content-Disposition: inline; filename="ro-crate-paper.pdf"
Link: <http://localhost:8080/doi/10.3897/biss.6.94630>; rel="cite-as"
Link: <http://localhost:8080/id/publication/ro-crate-paper.ttl>; rel="describedby"; type="text/turtle"
Link: <http://localhost:8080/id/publication/ro-crate-paper.html>; rel="describedby"; type="text/html"
```

---

### 3.6 API Service Endpoint & Catalog (PT-05 & PT-07)

#### Base API: `http://localhost:8080/api/observations/v1`
```bash
curl -I -X GET "http://localhost:8080/api/observations/v1"
```
```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
Link: <http://localhost:8080/id/dataset/arms-mbon>; rel="cite-as"
Link: <http://localhost:8080/.well-known/api-catalog>; rel="api-catalog"
Link: <http://localhost:8080/api/openapi.json>; rel="service-desc"; type="application/vnd.oai.openapi+json"
Link: <http://localhost:8080/api/docs/>; rel="service-doc"; type="text/html"
Link: <http://localhost:8080/id/service/marineinfo-api.ttl>; rel="service-meta"; type="text/turtle"
```

#### API Catalog: `http://localhost:8080/.well-known/api-catalog`
```bash
curl -I -X GET "http://localhost:8080/.well-known/api-catalog"
```
```http
HTTP/1.1 200 OK
Content-Type: application/linkset+json; charset=utf-8
Link: <http://localhost:8080/sitemap-catalog.xml>; rel="alternate"; type="application/xml"
Link: <http://localhost:8080/api/observations/v1>; rel="item"
```

---

### 3.7 Entity Conneg: `vliz` and `maregraph` (PT-03)

#### VLIZ Institute: `http://localhost:8080/id/institute/vliz`
```bash
curl -I -X GET "http://localhost:8080/id/institute/vliz"
```
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Link: <http://localhost:8080/id/institute/vliz.ttl>; rel="alternate"; type="text/turtle"
Link: <http://localhost:8080/id/institute/vliz.jsonld>; rel="alternate"; type="application/ld+json"
Link: <http://localhost:8080/id/institute/vliz.html>; rel="alternate"; type="text/html"
Link: <http://localhost:8080/id/institute/vliz.rdf>; rel="alternate"; type="application/rdf+xml"
Link: <http://localhost:8080/id/institute/vliz.linkset.json>; rel="linkset"; type="application/linkset+json"
```

#### Maregraph Project: `http://localhost:8080/id/project/maregraph`
```bash
curl -I -X GET "http://localhost:8080/id/project/maregraph"
```
```http
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Link: <http://localhost:8080/id/project/maregraph.ttl>; rel="alternate"; type="text/turtle"
Link: <http://localhost:8080/id/project/maregraph.jsonld>; rel="alternate"; type="application/ld+json"
Link: <http://localhost:8080/id/project/maregraph.html>; rel="alternate"; type="text/html"
Link: <http://localhost:8080/id/project/maregraph.linkset.json>; rel="linkset"; type="application/linkset+json"
```

---

## 4. RFC 9264 / RFC 9727 JSON Linksets Payload Reference

---

### 4.1 Master Linkset: `arms-mbon.linkset.json` (PT-03 & PT-08)
* **URI:** `http://localhost:8080/id/dataset/arms-mbon.linkset.json`
* **Content-Type:** `application/linkset+json`

```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8080/id/dataset/arms-mbon",
      "alternate": [
        {"href": "http://localhost:8080/id/dataset/arms-mbon.ttl", "type": "text/turtle"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.jsonld", "type": "application/ld+json"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.html", "type": "text/html"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.rdf", "type": "application/rdf+xml"}
      ],
      "profile": [
        {"href": "http://localhost:8080/id/profile/marine-genomic-dataset-profile"}
      ],
      "item": [
        {"href": "http://localhost:8080/id/dataset/arms-mbon.conneg.linkset.json", "type": "application/linkset+json"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.profiles.linkset.json", "type": "application/linkset+json"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.provenance.linkset.json", "type": "application/linkset+json"}
      ]
    }
  ]
}
```

---

### 4.2 Child Linksets (PT-08 Decomposition)

#### Child 1: Conneg Linkset (`arms-mbon.conneg.linkset.json`)
* **URI:** `http://localhost:8080/id/dataset/arms-mbon.conneg.linkset.json`
```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8080/id/dataset/arms-mbon.conneg.linkset.json",
      "collection": [
        {"href": "http://localhost:8080/id/dataset/arms-mbon.linkset.json"}
      ]
    },
    {
      "anchor": "http://localhost:8080/id/dataset/arms-mbon",
      "alternate": [
        {"href": "http://localhost:8080/id/dataset/arms-mbon.ttl", "type": "text/turtle"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.jsonld", "type": "application/ld+json"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.html", "type": "text/html"},
        {"href": "http://localhost:8080/id/dataset/arms-mbon.rdf", "type": "application/rdf+xml"}
      ]
    }
  ]
}
```

#### Child 2: Profiles Linkset (`arms-mbon.profiles.linkset.json`)
* **URI:** `http://localhost:8080/id/dataset/arms-mbon.profiles.linkset.json`
```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8080/id/dataset/arms-mbon.profiles.linkset.json",
      "collection": [
        {"href": "http://localhost:8080/id/dataset/arms-mbon.linkset.json"}
      ]
    },
    {
      "anchor": "http://localhost:8080/id/dataset/arms-mbon",
      "profile": [
        {"href": "http://localhost:8080/id/profile/marine-genomic-dataset-profile"}
      ]
    }
  ]
}
```

#### Child 3: Provenance Linkset (`arms-mbon.provenance.linkset.json`)
* **URI:** `http://localhost:8080/id/dataset/arms-mbon.provenance.linkset.json`
```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8080/id/dataset/arms-mbon.provenance.linkset.json",
      "collection": [
        {"href": "http://localhost:8080/id/dataset/arms-mbon.linkset.json"}
      ]
    },
    {
      "anchor": "http://localhost:8080/id/dataset/arms-mbon",
      "author": [
        {"href": "http://localhost:8080/id/institute/vliz"}
      ]
    }
  ]
}
```

---

### 4.3 RFC 9727 API Catalog: `/.well-known/api-catalog` (PT-07)
* **URI:** `http://localhost:8080/.well-known/api-catalog`
```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8080/.well-known/api-catalog",
      "item": [
        {"href": "http://localhost:8080/api/observations/v1"}
      ],
      "alternate": [
        {
          "href": "http://localhost:8080/sitemap-catalog.xml",
          "type": "application/xml"
        }
      ]
    },
    {
      "anchor": "http://localhost:8080/api/observations/v1",
      "service-desc": [
        {"href": "http://localhost:8080/api/openapi.json", "type": "application/vnd.oai.openapi+json"}
      ],
      "service-doc": [
        {"href": "http://localhost:8080/api/docs/", "type": "text/html"}
      ],
      "service-meta": [
        {"href": "http://localhost:8080/id/service/marineinfo-api.ttl", "type": "text/turtle"}
      ]
    }
  ]
}
```

---

### 4.4 Entity Linksets: `vliz.linkset.json` & `maregraph.linkset.json`

#### `vliz.linkset.json`
* **URI:** `http://localhost:8080/id/institute/vliz.linkset.json`
```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8080/id/institute/vliz",
      "alternate": [
        {"href": "http://localhost:8080/id/institute/vliz.ttl", "type": "text/turtle"},
        {"href": "http://localhost:8080/id/institute/vliz.jsonld", "type": "application/ld+json"},
        {"href": "http://localhost:8080/id/institute/vliz.html", "type": "text/html"},
        {"href": "http://localhost:8080/id/institute/vliz.rdf", "type": "application/rdf+xml"}
      ]
    }
  ]
}
```

#### `maregraph.linkset.json`
* **URI:** `http://localhost:8080/id/project/maregraph.linkset.json`
```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8080/id/project/maregraph",
      "alternate": [
        {"href": "http://localhost:8080/id/project/maregraph.ttl", "type": "text/turtle"},
        {"href": "http://localhost:8080/id/project/maregraph.jsonld", "type": "application/ld+json"},
        {"href": "http://localhost:8080/id/project/maregraph.html", "type": "text/html"}
      ]
    }
  ]
}
```

---

## 5. Master Link Relation Cross-Reference Table

This cross-reference table contains every link assertion tested across all 8 patterns:

| Subject / Anchor URI | Predicate / `rel` | Target / Object URI | Media Type / Profile | Tested in Pattern | Carrier Mechanism |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/id/dataset/arms-mbon` | `profile` | `/id/profile/marine-genomic-dataset-profile` | - | **PT-01** | Header, Linkset, Sitemap |
| `/id/profile/marine-genomic-dataset-profile` | `type` | `http://www.w3.org/ns/dx/prof/Profile` | - | **PT-01** | Header, RDF |
| `/id/profile/marine-genomic-dataset-profile` | `describedby` | `/id/profile/marine-genomic-dataset-profile.ttl` | `text/turtle` | **PT-01** | Header |
| `/id/dataset/north-sea-sensors` | `profile` | `/id/profile/marine-buoy-telemetry-profile` | - | **PT-01** | Header, Sitemap |
| `/id/profile/marine-buoy-telemetry-profile` | `type` | `http://www.w3.org/ns/dx/prof/Profile` | - | **PT-01** | Header, RDF |
| `/id/profile/marine-buoy-telemetry-profile` | `describedby` | `/id/profile/marine-buoy-telemetry-profile.ttl` | `text/turtle` | **PT-01** | Header |
| `/id/dataset/arms-2018` | `profile` | `/id/profile/marine-ecological-baseline-profile` | - | **PT-02** | Header, Sitemap |
| `/id/profile/marine-ecological-baseline-profile` | `http://schema.org/hasPart` | `/id/profile/schema-dataset-profile` | - | **PT-02** | Header, RDF |
| `/id/profile/marine-ecological-baseline-profile` | `http://schema.org/hasPart` | `/id/profile/dcat3-dataset-profile` | - | **PT-02** | Header, RDF |
| `/id/profile/marine-ecological-baseline-profile` | `http://schema.org/hasPart` | `/id/profile/darwin-core-occurrence-profile` | - | **PT-02** | Header, RDF |
| `/id/dataset/arms-mbon` | `alternate` | `/id/dataset/arms-mbon.{ttl,jsonld,html,rdf}` | Defined types | **PT-03** | Header, Linkset |
| `/id/dataset/arms-mbon` | `linkset` | `/id/dataset/arms-mbon.linkset.json` | `application/linkset+json` | **PT-03**, **PT-08** | Header |
| `/id/dataset/arms-mbon.{ttl,jsonld,html,rdf}` | `self` | `/id/dataset/arms-mbon` | - | **PT-03** | Header, HTML link |
| `/id/institute/vliz` | `alternate` | `/id/institute/vliz.{ttl,jsonld,html,rdf}` | Defined types | **PT-03** | Header, Linkset |
| `/id/institute/vliz.{ttl,jsonld,html,rdf}` | `self` | `/id/institute/vliz` | - | **PT-03** | Header, HTML link |
| `/id/project/maregraph` | `alternate` | `/id/project/maregraph.{ttl,jsonld,html}` | Defined types | **PT-03** | Header, Linkset |
| `/id/project/maregraph.{ttl,jsonld,html}` | `self` | `/id/project/maregraph` | - | **PT-03** | Header, HTML link |
| `/data/arms-mbon-18s.csv` | `cite-as` | `/doi/10.14284/578` | - | **PT-04** | Header |
| `/data/arms-mbon-18s.csv` | `describedby` | `/id/dataset/arms-mbon.{ttl,html}` | `text/turtle`, `text/html` | **PT-04** | Header |
| `/id/dataset/arms-mbon.{ttl,html}` | `describes` | `/id/dataset/arms-mbon` | - | **PT-04** | Header |
| `/data/arms-2018-samples.csv` | `cite-as` | `/doi/10.14284/412` | - | **PT-04** | Header |
| `/data/arms-2018-samples.csv` | `describedby` | `/id/dataset/arms-2018.{ttl,html}` | `text/turtle`, `text/html` | **PT-04** | Header |
| `/id/dataset/arms-2018.{ttl,html}` | `describes` | `/id/dataset/arms-2018` | - | **PT-04** | Header |
| `/data/ro-crate-paper.pdf` | `cite-as` | `/doi/10.3897/biss.6.94630` | - | **PT-04** | Header |
| `/data/ro-crate-paper.pdf` | `describedby` | `/id/publication/ro-crate-paper.{ttl,html}` | `text/turtle`, `text/html` | **PT-04** | Header |
| `/id/publication/ro-crate-paper.{ttl,html}` | `describes` | `/id/publication/ro-crate-paper` | - | **PT-04** | Header |
| `/api/observations/v1` | `cite-as` | `/id/dataset/arms-mbon` | - | **PT-05** | Header |
| `/api/observations/v1` | `api-catalog` | `/.well-known/api-catalog` | - | **PT-05**, **PT-07** | Header, Sitemap |
| `/api/observations/v1` | `service-desc` | `/api/openapi.json` | `application/vnd.oai.openapi+json` | **PT-05** | Header |
| `/api/observations/v1` | `service-doc` | `/api/docs/` | `text/html` | **PT-05** | Header |
| `/api/observations/v1` | `service-meta` | `/id/service/marineinfo-api.ttl` | `text/turtle` | **PT-05** | Header |
| `/robots.txt` | `sitemap` | `/sitemap.xml`, `/sitemap-catalog.xml` | `application/xml` | **PT-06**, **PT-07** | `robots.txt` |
| `/.well-known/api-catalog` | `alternate` | `/sitemap-catalog.xml` | `application/xml` | **PT-07** | Header, Linkset |
| `/.well-known/api-catalog` | `item` | `/api/observations/v1` | - | **PT-07** | Header, Linkset |
| `/id/dataset/arms-mbon.linkset.json` | `item` | `arms-mbon.{conneg,profiles,provenance}.linkset.json` | `application/linkset+json` | **PT-08** | Linkset |
| `arms-mbon.{conneg,profiles,provenance}.linkset.json` | `collection` | `/id/dataset/arms-mbon.linkset.json` | `application/linkset+json` | **PT-08** | Linkset |
