# GRMP Tests

A series of tests within the grmp framework. They are meant to run as containers while being managed by the grmp orchestrator.

### 1 Input Echo Test

A simple test meant as an example. It takes the configuration parameters from an input yml and tests:

1) whether the number of configuration parameters > 0
2) whether the value of each configuration parameter is not empty/None

It then creates a JUNIT XML file containing the results of the aforementioned tests and adds the configuration parameters, the number of configuration parameters and the number of empty parameters as testsuite properties.

### 2 Resource Availability

Checks DNS resolution and HTTP/HTTPS availability for one or more URLs. For each URL it tests:

1) whether the hostname resolves via DNS
2) whether the resource is reachable over HTTP (optional)
3) whether the resource is reachable over HTTPS (optional)

Redirect handling is configurable via a maximum redirect count. Redirects that cross the HTTP/HTTPS scheme boundary are treated as informational rather than failures. It then creates a JUNIT XML file containing the results and adds the tested URLs and hostnames as testsuite properties.

### 3 Check Certificate

Checks the TLS certificate expiration for one or more URLs. For each URL it tests:

1) whether the certificate can be retrieved
2) whether the certificate has not expired
3) whether the certificate expiry is not within a configurable threshold of days

It then creates a JUNIT XML file containing the results and adds the tested URLs, hostnames, timeout and certificate expiry threshold as testsuite properties.