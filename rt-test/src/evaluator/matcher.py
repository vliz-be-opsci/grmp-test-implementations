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
    error: Optional[str] = None
    skipped: bool = False
    skipped_message: str = ""
    stdout: str = ""
    stderr: str = ""
    matched_count: int = 0
    matched_links: List[WebLink] = field(default_factory=list)
    duration: float = 0.0
    properties: dict = field(default_factory=dict)
    suite_name: str = ""


def evaluate_relation_expectation(
    node: ResourceNode,
    exp: RelationExpectation,
    case_prefix: str = "",
) -> AssertionResult:
    """Evaluate a single relation expectation against a harvested ResourceNode."""
    rel_spec = f"rel={exp.rel}"
    if exp.target:
        rel_spec += f" target={exp.target}"
    elif exp.target_pattern:
        rel_spec += f" target_pattern={exp.target_pattern}"
    if exp.type:
        rel_spec += f" type={exp.type}"
    if exp.profile:
        rel_spec += f" profile={exp.profile}"

    if case_prefix:
        case_name = f"{case_prefix}rt_relation [{node.uri}] [{rel_spec}]"
    else:
        case_name = f"rt_relation [{node.uri}] [{rel_spec}]"

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
    error = None

    if node.error:
        passed = False
        error = node.error

    if passed:
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

    # Build comprehensive diagnostic stdout
    stdout_lines = [
        f"GET {node.uri}",
        f"HTTP Status: {node.status_code}",
        f"Content-Type: {node.content_type or 'none'}",
        (
            f"Discovered Links: {len(node.all_links)} total "
            f"({len(node.direct_links)} direct from Link headers/body, "
            f"{len(node.expanded_links)} expanded from {len(node.referenced_linksets)} linkset(s))"
        ),
        f"Evaluated Expectation: {exp.description()}",
        f"Matched Relations Count: {count}",
    ]
    if matching:
        stdout_lines.append("Matched Links:")
        for idx, ml in enumerate(matching, 1):
            line = f"  [{idx}] href=\"{ml.href}\" (rel=\"{ml.rel}\""
            if ml.media_type:
                line += f', type="{ml.media_type}"'
            if ml.profile:
                line += f', profile="{ml.profile}"'
            if ml.anchor and ml.anchor != node.uri:
                line += f', anchor="{ml.anchor}"'
            line += ")"
            stdout_lines.append(line)

    stderr_lines = []
    if error:
        stderr_lines.append(f"Harvest/Request error: {error}")
    elif failure_message:
        stderr_lines.append(f"Assertion failure: {failure_message}")
        if failure_text:
            stderr_lines.append(failure_text)

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
        error=error,
        stdout="\n".join(stdout_lines),
        stderr="\n".join(stderr_lines),
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
        case_name = (
            f"{case_prefix}rt_triples [{node.uri}] [min_triples={expect.min_triples}]"
            if case_prefix
            else f"rt_triples [{node.uri}] [min_triples={expect.min_triples}]"
        )
        passed = triple_count >= expect.min_triples
        failure_msg = None
        failure_txt = None
        if not passed:
            failure_msg = "Insufficient RDF triples found"
            failure_txt = f"URL: {node.uri}\nExpected >= {expect.min_triples} triples, found {triple_count}."

        stdout = "\n".join([
            f"RDF Triples Assertion for {node.uri}",
            f"Consolidated RDF Triples Count: {triple_count}",
            f"Required Minimum: {expect.min_triples}",
            f"Outcome: {'PASSED' if passed else 'FAILED'}",
        ])
        stderr = failure_txt or ""

        results.append(
            AssertionResult(
                case_name=case_name,
                target_url=node.uri,
                passed=passed,
                failure_message=failure_msg,
                failure_text=failure_txt,
                stdout=stdout,
                stderr=stderr,
                matched_count=triple_count,
                properties={"url": node.uri, "triples_found": str(triple_count), "min_triples": str(expect.min_triples)},
            )
        )

    if expect.sparql_ask:
        for idx, query in enumerate(expect.sparql_ask, start=1):
            case_name = (
                f"{case_prefix}rt_sparql [{node.uri}] [query_#{idx}]"
                if case_prefix
                else f"rt_sparql [{node.uri}] [query_#{idx}]"
            )
            passed = False
            failure_msg = None
            failure_txt = None
            error = None
            try:
                qres = full_graph.query(query)
                passed = bool(qres)
                if not passed:
                    failure_msg = "SPARQL ASK query returned False"
                    failure_txt = f"URL: {node.uri}\nQuery:\n{query}\nResult was False or empty."
            except Exception as exc:
                passed = False
                error = f"SPARQL query failed execution: {exc}"
                failure_txt = f"URL: {node.uri}\nQuery:\n{query}\nError: {exc}"

            stdout = "\n".join([
                f"SPARQL ASK Assertion #{idx} for {node.uri}",
                f"Consolidated Graph Triples Count: {triple_count}",
                f"SPARQL Query:\n{query.strip()}",
                f"Outcome: {'PASSED' if passed else ('ERROR' if error else 'FAILED')}",
            ])
            stderr = error or failure_txt or ""

            results.append(
                AssertionResult(
                    case_name=case_name,
                    target_url=node.uri,
                    passed=passed,
                    failure_message=failure_msg,
                    failure_text=failure_txt,
                    error=error,
                    stdout=stdout,
                    stderr=stderr,
                    properties={"url": node.uri, "sparql_query": query},
                )
            )

    return results
