"""
Evaluation and matching rules for relation and RDF expectations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from config.models import ExpectationConfig, RelationExpectation
from models.link import WebLink
from models.resource import ResourceNode


@dataclass
class AssertionResult:
    """Outcome of evaluating a single expectation."""

    case_name: str
    target_url: str
    passed: bool
    failure_message: Optional[str] = None
    failure_text: Optional[str] = None
    matched_count: int = 0
    matched_links: List[WebLink] = field(default_factory=list)
    duration: float = 0.0
    properties: dict = field(default_factory=dict)


def evaluate_relation_expectation(
    node: ResourceNode,
    exp: RelationExpectation,
    case_prefix: str = "",
) -> AssertionResult:
    """Evaluate a single relation expectation against a harvested ResourceNode."""
    case_name = f"{case_prefix}rel={exp.rel}" if case_prefix else f"rel={exp.rel}"
    if exp.target:
        case_name += f" (target={exp.target})"
    elif exp.target_pattern:
        case_name += f" (target_pattern={exp.target_pattern})"

    matching = node.all_links.find_links(
        rel=exp.rel,
        target=exp.target,
        target_pattern=exp.target_pattern,
        media_type=exp.type,
        profile=exp.profile,
    )
    count = len(matching)

    passed = True
    failure_message = None
    failure_text = None

    if exp.exists is True and count == 0:
        passed = False
        failure_message = f"Expected relation '{exp.rel}' was not found"
        failure_text = (
            f"Target URL: {node.uri}\n"
            f"Expected: {exp.description()}\n"
            f"Found: 0 matching relations among {len(node.all_links)} total links."
        )
    elif exp.exists is False and count > 0:
        passed = False
        failure_message = f"Forbidden relation '{exp.rel}' was found"
        failure_text = (
            f"Target URL: {node.uri}\n"
            f"Expected: {exp.description()}\n"
            f"Found: {count} forbidden relations."
        )
    elif exp.min_count is not None and count < exp.min_count:
        passed = False
        failure_message = f"Insufficient relations for '{exp.rel}'"
        failure_text = (
            f"Target URL: {node.uri}\n"
            f"Expected minimum {exp.min_count} relations matching: {exp.description()}\n"
            f"Found: {count} matching relations."
        )
    elif exp.max_count is not None and count > exp.max_count:
        passed = False
        failure_message = f"Too many relations for '{exp.rel}'"
        failure_text = (
            f"Target URL: {node.uri}\n"
            f"Expected maximum {exp.max_count} relations matching: {exp.description()}\n"
            f"Found: {count} matching relations."
        )
    elif exp.exact_count is not None and count != exp.exact_count:
        passed = False
        failure_message = f"Relation count mismatch for '{exp.rel}'"
        failure_text = (
            f"Target URL: {node.uri}\n"
            f"Expected exactly {exp.exact_count} relations matching: {exp.description()}\n"
            f"Found: {count} matching relations."
        )

    properties = {
        "url": node.uri,
        "rel": exp.rel,
        "matched_count": str(count),
        "total_links": str(len(node.all_links)),
        "status_code": str(node.status_code),
    }
    if exp.target:
        properties["expected_target"] = exp.target
    if exp.type:
        properties["expected_type"] = exp.type
    if exp.profile:
        properties["expected_profile"] = exp.profile

    return AssertionResult(
        case_name=case_name,
        target_url=node.uri,
        passed=passed,
        failure_message=failure_message,
        failure_text=failure_text,
        matched_count=count,
        matched_links=matching,
        properties=properties,
    )


def evaluate_triples_and_sparql(
    node: ResourceNode,
    expect: ExpectationConfig,
    case_prefix: str = "",
) -> List[AssertionResult]:
    """Evaluate optional min_triples and SPARQL ASK queries on the consolidated RDF graph."""
    results: List[AssertionResult] = []
    if expect.min_triples is None and not expect.sparql_ask:
        return results

    full_graph = node.build_full_graph()
    triple_count = len(full_graph)

    if expect.min_triples is not None:
        case_name = f"{case_prefix}min_triples ({expect.min_triples})" if case_prefix else f"min_triples ({expect.min_triples})"
        passed = triple_count >= expect.min_triples
        failure_msg = None
        failure_txt = None
        if not passed:
            failure_msg = "Insufficient RDF triples found"
            failure_txt = f"URL: {node.uri}\nExpected >= {expect.min_triples} triples, found {triple_count}."
        results.append(
            AssertionResult(
                case_name=case_name,
                target_url=node.uri,
                passed=passed,
                failure_message=failure_msg,
                failure_text=failure_txt,
                matched_count=triple_count,
                properties={"url": node.uri, "triples_found": str(triple_count), "min_triples": str(expect.min_triples)},
            )
        )

    if expect.sparql_ask:
        for idx, query in enumerate(expect.sparql_ask, start=1):
            case_name = f"{case_prefix}sparql_ask #{idx}" if case_prefix else f"sparql_ask #{idx}"
            passed = False
            failure_msg = None
            failure_txt = None
            try:
                qres = full_graph.query(query)
                passed = bool(qres)
                if not passed:
                    failure_msg = "SPARQL ASK query returned False"
                    failure_txt = f"URL: {node.uri}\nQuery: {query}\nResult was False or empty."
            except Exception as exc:
                passed = False
                failure_msg = "SPARQL query failed execution"
                failure_txt = f"URL: {node.uri}\nQuery: {query}\nError: {exc}"

            results.append(
                AssertionResult(
                    case_name=case_name,
                    target_url=node.uri,
                    passed=passed,
                    failure_message=failure_msg,
                    failure_text=failure_txt,
                    properties={"url": node.uri, "sparql_query": query},
                )
            )

    return results
