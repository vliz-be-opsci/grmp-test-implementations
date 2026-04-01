# GRMP Tests

A series of tests within the GRMP framework. They are meant to run as containers while being managed by the GRMP orchestrator.

### 1 Input Echo Test

A simple test meant as an example. It takes the configuration parameters from an input YAML and tests:

1) whether the number of configuration parameters > 0
2) whether the value of each configuration parameter is not empty or `None`

It then creates a JUnit XML file containing the results and adds the configuration parameters as testsuite properties. Parameter counts are reported in the test case output rather than as properties.

### 2 Resource Availability

Checks DNS resolution and HTTP/HTTPS availability for one or more URLs. For each URL it tests:

1) whether the hostname resolves via DNS
2) whether the resource is reachable over HTTP (optional)
3) whether the resource is reachable over HTTPS (optional)

Redirect handling is configurable via a maximum redirect count. Redirects that cross the HTTP/HTTPS scheme boundary are treated as informational rather than failures. It then creates a JUnit XML file containing the results and adds the tested URLs, hostnames and all configuration parameters as testsuite properties.

### 3 Check Certificate

Checks the TLS certificate expiration for one or more URLs. For each URL it produces a single test case that checks whether the certificate can be retrieved, whether it has already expired, and whether it will expire within a configurable threshold of days. SSL verification is intentionally disabled during retrieval so that expired certificates can still be evaluated. It then creates a JUnit XML file containing the results and adds the tested URLs, hostnames, timeout and certificate expiry threshold as testsuite properties.

### 4 CORS Compliance

Checks CORS header compliance for one or more URLs. For each URL it tests:

1) whether `access-control-allow-origin` correctly allows the configured origin(s)
2) whether `access-control-allow-methods` advertises at least the configured methods (optional)
3) whether `access-control-allow-headers` advertises at least the configured headers (optional)
4) whether `access-control-expose-headers` exposes at least the configured headers (optional)
5) whether HTTP redirects to HTTPS and whether CORS headers survive the redirect (optional)

Origin checks use an OPTIONS preflight request; expose-header checks use a GET request. It then creates a JUnit XML file containing the results and adds the tested URLs, hostnames and all configuration parameters as testsuite properties.

### 5 Content Negotiation

Checks whether one or more URLs correctly honour HTTP content negotiation via the `Accept` request header. For each URL and configured `Accept` header value it tests:

1) whether the server responds with a `2xx` status code
2) whether the response `Content-Type` matches the requested type(s)
3) whether the response body conforms to its advertised content type (optional, RDF types only)

Both simple `Accept` headers (single type, exact match) and complex headers (multiple types with quality weights, subset match) are supported. Body conformity is checked by parsing the response body using rdflib. It then creates a JUnit XML file containing the results and adds the tested URLs, hostnames and all configuration parameters as testsuite properties.

### 6 SHACL Validation

Checks whether RDF graphs harvested from one or more data URLs conform to a given SHACL shapes graph. For each data URL it:

1) harvests the data URL into an RDF graph using the `py-sema` library
2) validates the data graph against the SHACL shapes graph using `pyshacl`
3) reports conformance (pass) or non-conformance with the validation report text (fail)

The shapes graph is harvested once from the configured `TEST_SHAPES_URL`. It then creates a JUnit XML file containing the results and adds the shapes URL and all tested data URLs as testsuite properties.

### 7 LDES Validation

Checks whether one or more URLs expose a valid Linked Data Event Stream (LDES). For each URL it tests:

1) whether the URL can be fetched and parsed as an RDF graph
2) whether the graph contains at least one `ldes:EventStream` declaration (`rdf:type ldes:EventStream`)
3) whether each declared event stream has at least one `tree:view` relation
4) whether the stream exposes at least the configured minimum number of `ldes:member` triples (optional, controlled by `TEST_MIN-MEMBERS`)
5) whether the stream exposes at least the configured minimum number of tree fragments (`tree:Node` resources reachable via `tree:view` or `tree:node`, optional, controlled by `TEST_MIN-FRAGMENTS`)
6) whether the members in the stream's graph conform to a SHACL shapes graph (optional, controlled by `TEST_SHAPES-URL`)

If the RDF harvest fails the subsequent checks are reported as skipped. Similarly, if no `ldes:EventStream` is found the remaining checks are skipped. The `min_members`, `min_fragments` and SHACL checks are only run when their respective configuration parameters are provided. It then creates a JUnit XML file containing the results and adds the tested URLs, configuration thresholds and the SHACL shapes URL as testsuite properties.