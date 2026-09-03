"""
Tests for anchor transparency, display representations, and ASCII diagram rendering.
"""

import os
from tempfile import NamedTemporaryFile
from junitparser import JUnitXml

from src.config.models import ExpectationConfig, RelationExpectation, TestCaseConfig
from src.evaluator.matcher import evaluate_relation_expectation, AssertionResult
from src.evaluator.runner import SuiteRunner
from src.models.link import LinkSet, WebLink
from src.models.resource import ResourceNode
from src.reporter.diagram import ASCIIDiagramRenderer
from src.reporter.junit import generate_junit_xml


def test_weblink_anchor_guarantees_and_display_repr():
    # 1. Non-empty anchor is preserved
    link1 = WebLink(anchor="https://example.org/dataset/1", href="https://example.org/profile/1", rel="profile")
    assert link1.anchor == "https://example.org/dataset/1"
    assert link1.display_repr() == 'anchor="https://example.org/dataset/1" -> rel="profile" -> href="https://example.org/profile/1"'

    # 2. Empty anchor automatically falls back to href
    link2 = WebLink(anchor="", href="https://example.org/doc.html", rel="describedby", media_type="text/html", source="http_header")
    assert link2.anchor == "https://example.org/doc.html"
    assert 'anchor="https://example.org/doc.html"' in link2.display_repr()
    assert 'type="text/html"' in link2.display_repr()
    assert 'source="http_header"' in link2.display_repr()


def test_relation_expectation_anchor_filtering():
    node = ResourceNode(uri="https://example.org/resource")
    # Add two links with different anchors (e.g. from expanded linkset)
    node.direct_links.add(
        WebLink(
            anchor="https://example.org/resource",
            href="https://example.org/doi/123",
            rel="cite-as",
        )
    )
    node.direct_links.add(
        WebLink(
            anchor="https://example.org/other-context",
            href="https://example.org/doi/123",
            rel="cite-as",
        )
    )

    # 1. Match specific anchor
    exp_anchor1 = RelationExpectation(rel="cite-as", anchor="https://example.org/resource", exists=True)
    res1 = evaluate_relation_expectation(node, exp_anchor1)
    assert res1.passed is True
    assert res1.matched_count == 1
    assert res1.matched_links[0].anchor == "https://example.org/resource"

    # 2. Match anchor pattern regex
    exp_pat = RelationExpectation(rel="cite-as", anchor_pattern=r"other-context$", exists=True)
    res_pat = evaluate_relation_expectation(node, exp_pat)
    assert res_pat.passed is True
    assert res_pat.matched_count == 1
    assert res_pat.matched_links[0].anchor == "https://example.org/other-context"

    # 3. Mismatched anchor fails
    exp_mismatch = RelationExpectation(rel="cite-as", anchor="https://example.org/nonexistent", exists=True)
    res_mis = evaluate_relation_expectation(node, exp_mismatch)
    assert res_mis.passed is False


def test_diagram_renderer_pt01_to_pt08_and_generic():
    harvest_node = ResourceNode(
        uri="https://example.org/dataset/arms",
        status_code=200,
        content_type="text/html",
        direct_links=LinkSet(links=[
            WebLink(anchor="https://example.org/dataset/arms", href="https://example.org/profile/p1", rel="profile", source="http_header")
        ]),
    )

    # PT-01
    res_pt01 = AssertionResult(
        case_name="PT-01 Test",
        target_url="https://example.org/dataset/arms",
        passed=True,
        matched_count=1,
        matched_links=harvest_node.direct_links.links,
        pattern_id="PT-01",
        pattern_roles={"resource": "https://example.org/dataset/arms", "profile": "https://example.org/profile/p1"},
        harvest_node=harvest_node,
    )
    diag_01 = ASCIIDiagramRenderer.render_assertion_result(res_pt01, {"https://example.org/dataset/arms": harvest_node}, include_trace=True)
    assert "[✓ PASS]" in diag_01
    assert "rel=\"profile\"" in diag_01
    assert "HTTP Call Trace & Provenance:" in diag_01

    # PT-04 (No Landing Page Failure - diagram only by default)
    res_pt04 = AssertionResult(
        case_name="PT-04 Test",
        target_url="https://example.org/data/samples.csv",
        passed=False,
        failure_message="Missing rel=describedby",
        failure_text="Target URL: https://example.org/data/samples.csv",
        pattern_id="PT-04",
        pattern_roles={
            "pid": "https://doi.org/10.1234/test",
            "content": "https://example.org/data/samples.csv",
            "descriptions": ["https://example.org/meta.ttl"],
        },
        harvest_node=ResourceNode(uri="https://example.org/data/samples.csv", status_code=200, content_type="text/csv"),
    )
    diag_04 = ASCIIDiagramRenderer.render_assertion_result(res_pt04)
    assert "[✗ FAILED]" in diag_04
    assert "Content Payload" in diag_04
    assert "[✗ MISSING]" in diag_04
    assert "HTTP Call Trace & Provenance:" not in diag_04

    # Raw / Generic Assertion
    res_generic = AssertionResult(
        case_name="Raw Assertion",
        target_url="https://example.org/api",
        passed=True,
        matched_count=1,
        matched_links=[WebLink(anchor="https://example.org/api", href="https://example.org/docs", rel="service-doc")],
        harvest_node=ResourceNode(uri="https://example.org/api", status_code=200),
    )
    diag_gen = ASCIIDiagramRenderer.render_assertion_result(res_generic)
    assert "Target Resource: https://example.org/api" in diag_gen
    assert "[✓ PASS]" in diag_gen


def test_junit_xml_includes_diagram_and_anchor_representation():
    harvest_node = ResourceNode(
        uri="https://example.org/dataset/fail",
        status_code=404,
        content_type="text/html",
        error="Not Found",
    )
    res = AssertionResult(
        case_name="[PT-01] Profile Conformance Failure",
        target_url="https://example.org/dataset/fail",
        passed=False,
        failure_message="Expected relation 'profile' was not found",
        failure_text="Expected profile link.",
        pattern_id="PT-01",
        pattern_roles={"resource": "https://example.org/dataset/fail", "profile": "https://example.org/profile/1"},
        harvest_node=harvest_node,
    )
    diag = ASCIIDiagramRenderer.render_assertion_result(res, {"https://example.org/dataset/fail": harvest_node})
    res.diagram = diag
    res.stdout = f"GET {harvest_node.uri}\n\n{diag}"
    res.failure_text = f"{res.failure_text}\n\n{diag}"

    with NamedTemporaryFile(suffix=".xml", delete=False) as tf:
        tmp_path = tf.name

    try:
        generate_junit_xml(
            suite_name="test-suite",
            results=[res],
            output_file=tmp_path,
        )
        xml = JUnitXml.fromfile(tmp_path)
        testsuite = next(iter(xml))
        testcase = next(iter(testsuite))
        assert testcase.is_failure
        assert "DIAGRAM: [PT-01] Profile Conformance Failure" in testcase.result[0].text
        assert "HTTP Call Trace & Provenance:" not in testcase.result[0].text
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_concise_stdout_on_passed_test_vs_full_trace_on_failure():
    # Node with 1 matching link and 5 other unrelated links
    node = ResourceNode(
        uri="https://example.org/dataset/1",
        status_code=200,
        content_type="text/html",
        direct_links=LinkSet(links=[
            WebLink(anchor="https://example.org/dataset/1", href="https://example.org/profile/p1", rel="profile"),
            WebLink(anchor="https://example.org/dataset/1", href="https://example.org/unrelated-1", rel="unrelated-rel-1"),
            WebLink(anchor="https://example.org/dataset/1", href="https://example.org/unrelated-2", rel="unrelated-rel-2"),
            WebLink(anchor="https://example.org/dataset/1", href="https://example.org/unrelated-3", rel="unrelated-rel-3"),
        ]),
    )

    # 1. Passed test result (with include_trace=True)
    res_passed = AssertionResult(
        case_name="Passing profile test",
        target_url="https://example.org/dataset/1",
        passed=True,
        matched_count=1,
        matched_links=[WebLink(anchor="https://example.org/dataset/1", href="https://example.org/profile/p1", rel="profile")],
        harvest_node=node,
    )
    diag_passed = ASCIIDiagramRenderer.render_assertion_result(res_passed, {"https://example.org/dataset/1": node}, include_trace=True)
    assert "https://example.org/profile/p1" in diag_passed
    assert "unrelated-rel-1" not in diag_passed
    assert "unrelated-rel-2" not in diag_passed
    assert "unrelated-rel-3" not in diag_passed

    # 2. Failed test result (with include_trace=True)
    res_failed = AssertionResult(
        case_name="Failing license test",
        target_url="https://example.org/dataset/1",
        passed=False,
        failure_message="Missing license link",
        matched_count=0,
        matched_links=[],
        harvest_node=node,
    )
    diag_failed = ASCIIDiagramRenderer.render_assertion_result(res_failed, {"https://example.org/dataset/1": node}, include_trace=True)
    assert "unrelated-rel-1" in diag_failed
    assert "unrelated-rel-2" in diag_failed
    assert "unrelated-rel-3" in diag_failed

    # 3. Failed test in default diagram-only mode (error text / failure diagram)
    diag_failed_only = ASCIIDiagramRenderer.render_assertion_result(res_failed, {"https://example.org/dataset/1": node}, include_trace=False)
    assert "DIAGRAM: Failing license test" in diag_failed_only
    assert "HTTP Call Trace & Provenance:" not in diag_failed_only


def test_render_pt09_diagram():
    node_series = ResourceNode(
        uri="https://example.org/id/dataset/90",
        status_code=200,
        direct_links=LinkSet(links=[
            WebLink(anchor="https://example.org/id/dataset/90", href="https://example.org/id/dataset/90/v2.1", rel="latest-version"),
            WebLink(anchor="https://example.org/id/dataset/90", href="https://example.org/id/dataset/90/history", rel="version-history"),
            WebLink(anchor="https://example.org/id/dataset/90", href="https://doi.org/10.14284/90", rel="cite-as"),
        ]),
    )
    res = AssertionResult(
        case_name="[PT-09] Dataset 90 Release Linking",
        target_url="https://example.org/id/dataset/90",
        passed=True,
        pattern_id="PT-09",
        pattern_roles={
            "series": "https://example.org/id/dataset/90",
            "latest_version": "https://example.org/id/dataset/90/v2.1",
            "version_history": "https://example.org/id/dataset/90/history",
            "series_pid": "https://doi.org/10.14284/90",
            "releases": [
                {
                    "uri": "https://example.org/id/dataset/90/v2.1",
                    "version": "2.1",
                    "predecessor": "https://example.org/id/dataset/90/v2.0",
                },
                {
                    "uri": "https://example.org/id/dataset/90/v2.0",
                    "version": "2.0",
                    "predecessor": "https://example.org/id/dataset/90/v1.0",
                    "successor": "https://example.org/id/dataset/90/v2.1",
                },
            ],
        },
    )
    diag = ASCIIDiagramRenderer.render_assertion_result(res, {"https://example.org/id/dataset/90": node_series}, include_trace=False)
    assert "Conceptual Series (Latest Identity): https://example.org/id/dataset/90" in diag
    assert "Latest Authoritative Release: https://example.org/id/dataset/90/v2.1" in diag
    assert "rel=\"version-history\" ---> https://example.org/id/dataset/90/history" in diag
    assert "Version Succession Chain (RFC 5829):" in diag
    assert "[LATEST v2.1]" in diag
    assert "[v2.0]" in diag


def test_console_reporting_grouped_and_flat(capsys):
    from src.reporter.console import print_flat_results, print_grouped_results
    node = ResourceNode(uri="https://example.org/dataset/90", status_code=200, content_type="text/turtle", duration=0.012)
    link = WebLink(anchor="https://example.org/dataset/90", rel="latest-version", href="https://example.org/dataset/90/v2.1", source="http_header")
    node.direct_links.add(link)
    node.all_links.add(link)

    res = AssertionResult(
        case_name="rt_relation [https://example.org/dataset/90] [rel=latest-version target=https://example.org/dataset/90/v2.1]",
        target_url="https://example.org/dataset/90",
        passed=True,
        suite_name="[PT-09] Dataset 90 Release Lifecycle",
        harvest_node=node,
        matched_links=[link],
    )

    print_grouped_results([res], diagram_mode="never")
    captured = capsys.readouterr().out
    assert "[PT-09] Dataset 90 Release Lifecycle" in captured
    assert "Target: https://example.org/dataset/90 (HTTP 200 text/turtle" in captured
    assert "[✓ PASS]" in captured
    assert "[source: http_header]" in captured

    print_flat_results([res], diagram_mode="never", detailed=True)
    captured_flat = capsys.readouterr().out
    assert "[✓ PASSED]" in captured_flat
    assert "source: http_header" in captured_flat


def test_render_pt01_diagram_with_alternate_and_type():
    res_node = ResourceNode(uri="https://example.org/dataset/1", status_code=200)
    res_node.all_links.add(WebLink(anchor="https://example.org/dataset/1", rel="profile", href="https://example.org/profile/p1"))

    prof_node = ResourceNode(uri="https://example.org/profile/p1", status_code=200)
    prof_node.all_links.add(WebLink(anchor="https://example.org/profile/p1", rel="type", href="http://www.w3.org/ns/dx/prof/Profile"))
    prof_node.all_links.add(WebLink(anchor="https://example.org/profile/p1", rel="alternate", href="https://example.org/profile/p1.ttl"))

    res = AssertionResult(
        case_name="rt_relation [https://example.org/dataset/1] [rel=profile]",
        target_url="https://example.org/dataset/1",
        passed=True,
        pattern_id="PT-01",
        pattern_roles={
            "resource": "https://example.org/dataset/1",
            "profile": "https://example.org/profile/p1",
            "profile_type": "http://www.w3.org/ns/dx/prof/Profile",
            "profile_alternate": "https://example.org/profile/p1.ttl",
        },
    )

    nodes = {
        "https://example.org/dataset/1": res_node,
        "https://example.org/profile/p1": prof_node,
    }
    diag = ASCIIDiagramRenderer.render_assertion_result(res, nodes)
    assert "Resource: https://example.org/dataset/1" in diag
    assert "Profile: https://example.org/profile/p1" in diag
    assert 'rel="profile"' in diag
    assert 'rel="type"' in diag
    assert 'rel="alternate"' in diag
    assert "https://example.org/profile/p1.ttl" in diag
    assert "http://www.w3.org/ns/dx/prof/Profile" in diag


def test_render_pt01_diagram_with_profile_description_type():
    res_node = ResourceNode(uri="https://example.org/dataset/1", status_code=200)
    res_node.direct_links.add(WebLink(anchor="https://example.org/dataset/1", rel="profile", href="https://example.org/profile/p1"))

    prof_node = ResourceNode(uri="https://example.org/profile/p1", status_code=200)
    prof_node.direct_links.add(WebLink(anchor="https://example.org/profile/p1", rel="describedby", href="https://example.org/profile/p1.ttl"))
    prof_node.direct_links.add(WebLink(anchor="https://example.org/profile/p1", rel="type", href="https://www.rfc-editor.org/info/rfc6906"))

    desc_node = ResourceNode(uri="https://example.org/profile/p1.ttl", status_code=200)
    desc_node.direct_links.add(WebLink(anchor="https://example.org/profile/p1.ttl", rel="type", href="http://www.w3.org/ns/dx/prof/Profile"))

    res = AssertionResult(
        case_name="rt_relation [https://example.org/dataset/1] [rel=profile]",
        target_url="https://example.org/dataset/1",
        passed=True,
        pattern_id="PT-01",
        pattern_roles={
            "resource": "https://example.org/dataset/1",
            "profile": "https://example.org/profile/p1",
            "profile_description": "https://example.org/profile/p1.ttl",
            "profile_description_type": "http://www.w3.org/ns/dx/prof/Profile",
            "profile_type": "https://www.rfc-editor.org/info/rfc6906",
        },
    )

    nodes = {
        "https://example.org/dataset/1": res_node,
        "https://example.org/profile/p1": prof_node,
        "https://example.org/profile/p1.ttl": desc_node,
    }
    diag = ASCIIDiagramRenderer.render_assertion_result(res, nodes)
    assert 'rel="describedby" -> https://example.org/profile/p1.ttl' in diag
    assert 'rel="type"        -> http://www.w3.org/ns/dx/prof/Profile' in diag
    assert 'rel="type"        -> https://www.rfc-editor.org/info/rfc6906' in diag
    assert "[✓ PASS]" in diag



def test_diagram_renderer_pt06_indented_resources():
    sm_node = ResourceNode(uri="https://example.org/sitemap.xml", status_code=200)
    sm_node.all_links.add(WebLink(anchor="https://example.org/sitemap.xml", rel="item", href="https://example.org/id/dataset/arms"))
    sm_node.all_links.add(WebLink(anchor="https://example.org/id/dataset/arms", rel="linkset", href="https://example.org/id/dataset/arms.linkset.json"))
    sm_node.all_links.add(WebLink(anchor="https://example.org/id/dataset/arms", rel="alternate", href="https://example.org/id/dataset/arms.ttl"))

    robots_node = ResourceNode(uri="https://example.org/robots.txt", status_code=200)
    robots_node.all_links.add(WebLink(anchor="https://example.org/robots.txt", rel="item", href="https://example.org/sitemap.xml"))

    res = AssertionResult(
        case_name="PT-06 Test",
        target_url="https://example.org/sitemap.xml",
        passed=True,
        pattern_id="PT-06",
        pattern_roles={
            "host": "https://example.org",
            "robots_txt": True,
            "sitemap": "https://example.org/sitemap.xml",
            "resources": [
                {
                    "uri": "https://example.org/id/dataset/arms",
                    "linkset": "https://example.org/id/dataset/arms.linkset.json",
                    "alternates": ["https://example.org/id/dataset/arms.ttl"],
                    "profile": "https://example.org/profile/arms",
                }
            ],
        },
    )

    nodes = {
        "https://example.org/robots.txt": robots_node,
        "https://example.org/sitemap.xml": sm_node,
    }
    diag = ASCIIDiagramRenderer.render_assertion_result(res, nodes)
    assert "Host: https://example.org" in diag
    assert "robots.txt: https://example.org/robots.txt" in diag
    assert "sitemap.xml: https://example.org/sitemap.xml" in diag
    assert "https://example.org/id/dataset/arms" in diag
    assert "+--- linkset: https://example.org/id/dataset/arms.linkset.json" in diag
    assert "+--- alternate: https://example.org/id/dataset/arms.ttl" in diag
    assert "+--- profile: https://example.org/profile/arms" in diag

    # Test robots_txt: False
    res_no_robots = AssertionResult(
        case_name="PT-06 Test No Robots",
        target_url="https://example.org/sitemap.xml",
        passed=True,
        pattern_id="PT-06",
        pattern_roles={
            "host": "https://example.org",
            "robots_txt": False,
            "sitemap": "https://example.org/sitemap.xml",
            "resources": ["https://example.org/id/dataset/arms"],
        },
    )
    diag_no_robots = ASCIIDiagramRenderer.render_assertion_result(res_no_robots, nodes)
    assert "v (direct sitemap)" in diag_no_robots
    assert "robots.txt" not in diag_no_robots


def test_diagram_renderer_pt06_alternate_consistency_perspectives():
    res_uri = "https://example.org/id/dataset/arms-mbon"
    ls_uri = "https://example.org/id/dataset/arms-mbon.linkset.json"
    alt_uri = "https://example.org/id/dataset/arms-mbon.ttl"
    prof_uri = "https://example.org/profile/genomic"

    # 1. Sitemap node
    sm_node = ResourceNode(uri="https://example.org/sitemap.xml", status_code=200)
    sm_node.direct_links.add(WebLink(anchor="https://example.org/sitemap.xml", rel="item", href=res_uri))
    sm_node.direct_links.add(WebLink(anchor=res_uri, rel="linkset", href=ls_uri))
    sm_node.direct_links.add(WebLink(anchor=res_uri, rel="alternate", href=alt_uri))
    sm_node.direct_links.add(WebLink(anchor=res_uri, rel="profile", href=prof_uri))

    # 2. Resource node
    res_node = ResourceNode(uri=res_uri, status_code=200)
    res_node.direct_links.add(WebLink(anchor=res_uri, rel="linkset", href=ls_uri))
    res_node.direct_links.add(WebLink(anchor=res_uri, rel="alternate", href=alt_uri))
    res_node.direct_links.add(WebLink(anchor=res_uri, rel="profile", href=prof_uri))

    # 3. Linkset node
    ls_node = ResourceNode(uri=ls_uri, status_code=200)
    ls_node.direct_links.add(WebLink(anchor=res_uri, rel="alternate", href=alt_uri))
    ls_node.direct_links.add(WebLink(anchor=res_uri, rel="profile", href=prof_uri))

    nodes = {
        "https://example.org/sitemap.xml": sm_node,
        res_uri: res_node,
        ls_uri: ls_node,
    }

    # Assertion result for alternate consistency test case
    res = AssertionResult(
        case_name=f"[PT-06] Sitemaps & Robots - Resource Linkset [{ls_uri}] Alternate Consistency",
        target_url=ls_uri,
        passed=True,
        pattern_id="PT-06",
        pattern_roles={
            "host": "https://example.org",
            "robots_txt": True,
            "sitemap": "https://example.org/sitemap.xml",
            "resources": [
                {
                    "uri": res_uri,
                    "linkset": ls_uri,
                    "alternates": [alt_uri],
                    "profile": prof_uri,
                }
            ],
        },
    )

    diag = ASCIIDiagramRenderer.render_assertion_result(res, nodes)
    assert "Alternate Resources & Consistency Analysis" in diag
    assert "[1] Sitemap Perspective" in diag
    assert "[2] Resource Headers Perspective" in diag
    assert "[3] Linkset Perspective" in diag
    assert "Consistency Triangulation Matrix:" in diag
    assert "[✓ IN SYNC]" in diag
    assert alt_uri in diag
    assert ls_uri in diag
    assert prof_uri in diag


def test_render_pt07_tripartite_diagram():
    host_uri = "https://example.org"
    robots_uri = "https://example.org/robots.txt"
    sm_index_uri = "https://example.org/sitemap-index.xml"
    cat_uri = "https://example.org/.well-known/api-catalog"
    cat_sm_uri = "https://example.org/.well-known/api-catalog/sitemap-index.xml"
    ep_uri = "https://example.org/api/observations/v1"
    ep_sm_uri = "https://example.org/api/observations/v1/sitemap.xml"
    sub_uri = "https://example.org/api/observations/v1/fragments/1"

    # Robots node
    robots_node = ResourceNode(uri=robots_uri, status_code=200)
    robots_node.direct_links.add(WebLink(anchor=robots_uri, rel="item", href=sm_index_uri))

    # Sitemap Index node
    sm_index_node = ResourceNode(uri=sm_index_uri, status_code=200)
    sm_index_node.direct_links.add(WebLink(anchor=sm_index_uri, rel="item", href=cat_sm_uri))
    sm_index_node.direct_links.add(WebLink(anchor=sm_index_uri, rel="item", href=ep_sm_uri))

    # Catalog Sitemap node
    cat_sm_node = ResourceNode(uri=cat_sm_uri, status_code=200)
    cat_sm_node.direct_links.add(WebLink(anchor=cat_sm_uri, rel="self", href=cat_uri))
    cat_sm_node.direct_links.add(WebLink(anchor=cat_sm_uri, rel="item", href=ep_uri))

    # Catalog node
    cat_node = ResourceNode(uri=cat_uri, status_code=200)
    cat_node.direct_links.add(WebLink(anchor=cat_uri, rel="alternate", href=cat_sm_uri))
    cat_node.direct_links.add(WebLink(anchor=cat_uri, rel="item", href=ep_uri))

    # Endpoint node
    ep_node = ResourceNode(uri=ep_uri, status_code=200)
    ep_node.direct_links.add(WebLink(anchor=ep_uri, rel="api-catalog", href=cat_uri))
    ep_node.direct_links.add(WebLink(anchor=ep_uri, rel="alternate", href=ep_sm_uri))

    # Endpoint Sitemap node
    ep_sm_node = ResourceNode(uri=ep_sm_uri, status_code=200)
    ep_sm_node.direct_links.add(WebLink(anchor=ep_sm_uri, rel="self", href=ep_uri))
    ep_sm_node.direct_links.add(WebLink(anchor=ep_sm_uri, rel="item", href=sub_uri))

    # Subresource node
    sub_node = ResourceNode(uri=sub_uri, status_code=200)
    sub_node.direct_links.add(WebLink(anchor=sub_uri, rel="collection", href=ep_uri))

    nodes = {
        robots_uri: robots_node,
        sm_index_uri: sm_index_node,
        cat_sm_uri: cat_sm_node,
        cat_uri: cat_node,
        ep_uri: ep_node,
        ep_sm_uri: ep_sm_node,
        sub_uri: sub_node,
    }

    res = AssertionResult(
        case_name="[PT-07] Hostwide API Catalog - Listing & Alternates",
        target_url=cat_uri,
        passed=True,
        pattern_id="PT-07",
        pattern_roles={
            "host": host_uri,
            "robots_txt": True,
            "sitemap_index": sm_index_uri,
            "api_catalog": cat_uri,
            "api_catalog_sitemap": cat_sm_uri,
            "api_endpoints": [
                {
                    "uri": ep_uri,
                    "sitemap": ep_sm_uri,
                    "subresources": [sub_uri],
                }
            ],
        },
    )

    diag = ASCIIDiagramRenderer.render_assertion_result(res, nodes)
    assert "Host: https://example.org" in diag
    assert "robots.txt: https://example.org/robots.txt" in diag
    assert "[2] Sitemaps Hierarchy (sitemaps.org)" in diag
    assert "Catalog Sitemap: https://example.org/.well-known/api-catalog/sitemap-index.xml" in diag
    assert "API Sitemap:     https://example.org/api/observations/v1/sitemap.xml" in diag
    assert "[3] API Catalog (RFC 9727)" in diag
    assert "[1] API Services & Subresources" in diag
    assert 'rel="collection" uplink' in diag
    assert "[✓ PASS]" in diag

