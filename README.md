# GRMP Tests

A series of tests within the grmp framework. They are meant to run as containers while being managed by the grmp orchestrator.

### 1 Input Echo Test

A simple test meant as an example. It takes the configuration parameters from an input yml and tests:

1) whether the number of configuration parameters > 0
2) whether the value of each configuration parameter is not empty/None

It then creates a JUNIT XML file containing the results of the aforementioned tests and adds the configuration parameters, the number of configuration parameters and the number of empty parameters as testsuite properties.