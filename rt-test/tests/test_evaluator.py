"""
Unit tests for evaluation matcher and rules.
"""

from src.config.models import RelationExpectation, ExpectationConfig
from src.evaluator.matcher import evaluate_relation_expectation, evaluate_triples_and_sparql
from src.models.link import WebLink
from src.models.resource import ResourceNode


def test_evaluate_relation_expectation_exists_pass():
    node = ResourceNode(uri="https://example.org/dataset/1")
    node.direct_links.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://example.org/profiles/v1",
            rel="profile",
        )
    )

    exp = RelationExpectation(rel="profile", exists=True)
    res = evaluate_relation_expectation(node, exp)
    assert res.passed is True
    assert res.matched_count == 1


def test_evaluate_relation_expectation_target_mismatch():
    node = ResourceNode(uri="https://example.org/dataset/1")
    node.direct_links.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://example.org/profiles/other",
            rel="profile",
        )
    )

    exp = RelationExpectation(rel="profile", target="https://example.org/profiles/v1", exists=True)
    res = evaluate_relation_expectation(node, exp)
    assert res.passed is False
    assert res.failure_message is not None


def test_evaluate_relation_expectation_target_pattern():
    node = ResourceNode(uri="https://example.org/dataset/1")
    node.direct_links.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://doi.org/10.1234/example-doi",
            rel="cite-as",
        )
    )

    exp = RelationExpectation(rel="cite-as", target_pattern=r"^https://doi\.org/10\..*", exists=True)
    res = evaluate_relation_expectation(node, exp)
    assert res.passed is True
    assert res.matched_count == 1


def test_evaluate_relation_expectation_min_count():
    node = ResourceNode(uri="https://example.org/catalog")
    for i in range(5):
        node.direct_links.add(
            WebLink(
                anchor="https://example.org/catalog",
                href=f"https://example.org/dataset/{i}",
                rel="item",
            )
        )

    # Passes min 3
    exp_pass = RelationExpectation(rel="item", min_count=3)
    res_pass = evaluate_relation_expectation(node, exp_pass)
    assert res_pass.passed is True

    # Fails min 10
    exp_fail = RelationExpectation(rel="item", min_count=10)
    res_fail = evaluate_relation_expectation(node, exp_fail)
    assert res_fail.passed is False


def test_evaluate_triples_and_sparql():
    node = ResourceNode(uri="https://example.org/dataset/1")
    node.direct_links.add(
        WebLink(
            anchor="https://example.org/dataset/1",
            href="https://example.org/profiles/v1",
            rel="profile",
        )
    )

    expect = ExpectationConfig(
        min_triples=1,
        sparql_ask=[
            "ASK { <https://example.org/dataset/1> <https://www.iana.org/assignments/relation/profile> ?o }"
        ],
    )
    results = evaluate_triples_and_sparql(node, expect)
    assert len(results) == 2
    assert results[0].passed is True
    assert results[1].passed is True
