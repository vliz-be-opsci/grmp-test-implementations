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
