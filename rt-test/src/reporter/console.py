"""
Console report renderer for RT test results.
Provides informative hierarchical grouped output, link carrier provenance,
and HTTP harvest details.
"""

from __future__ import annotations

from typing import Dict, List
from evaluator.matcher import AssertionResult

LINE_WIDTH = 100


def _format_expectation_label(res: AssertionResult) -> str:
    """Extract a concise assertion label from RelationExpectation or case_name."""
    exp = getattr(res, "expectation", None)
    if exp:
        parts = [f'rel="{exp.rel}"']
        if exp.target:
            parts.append(f'-> {exp.target}')
        elif exp.target_pattern:
            parts.append(f'pattern="{exp.target_pattern}"')
        if exp.type:
            parts.append(f'type="{exp.type}"')
        if exp.profile:
            parts.append(f'profile="{exp.profile}"')
        if exp.anchor:
            parts.append(f'anchor="{exp.anchor}"')
        if exp.min_count is not None:
            parts.append(f'min={exp.min_count}')
        if exp.exact_count is not None:
            parts.append(f'exact={exp.exact_count}')
        return " ".join(parts)

    case = res.case_name
    if "rt_relation " in case:
        idx = case.find("] [")
        if idx != -1:
            return case[idx + 3 : -1].replace("rel=", 'rel="').replace(" target=", '" -> ')
    elif "rt_harvest [" in case:
        url = case.replace("rt_harvest [", "").replace("]", "")
        return f"Harvest / Reachability on {url}"

    return case


def _format_source_badge(matched_links) -> str:
    """Format carrier provenance badges (http_header, linkset_json, html_head)."""
    if not matched_links:
        return ""
    sources = []
    seen = set()
    for link in matched_links:
        src = getattr(link, "source", None)
        if src and src not in seen:
            seen.add(src)
            sources.append(src)
    if sources:
        return f"[source: {', '.join(sources)}]"
    return ""


def print_grouped_results(
    results: List[AssertionResult],
    diagram_mode: str = "on-failure",
) -> None:
    """
    Print test results grouped hierarchically by Test Case (suite_name) and Target URL.
    Displays HTTP status, response time, link counts, and carrier source for each rule.
    """
    suites: Dict[str, List[AssertionResult]] = {}
    for res in results:
        s_name = res.suite_name or "General Assertions"
        suites.setdefault(s_name, []).append(res)

    for suite_name, suite_results in suites.items():
        print(f"\n{'─' * LINE_WIDTH}")
        print(f"{suite_name}")

        targets: Dict[str, List[AssertionResult]] = {}
        for res in suite_results:
            targets.setdefault(res.target_url, []).append(res)

        for target_url, target_results in targets.items():
            first_node = next((r.harvest_node for r in target_results if r.harvest_node), None)
            if first_node:
                status_str = f"HTTP {first_node.status_code}" if first_node.status_code else "HTTP ERROR"
                ct_str = f" {first_node.content_type}" if first_node.content_type else ""
                dur_str = f" in {first_node.duration:.3f}s" if getattr(first_node, "duration", 0) > 0 else ""
                dir_cnt = len(first_node.direct_links)
                exp_cnt = len(first_node.expanded_links)
                ls_cnt = len(first_node.referenced_linksets)

                link_summary = f"{len(first_node.all_links)} links ({dir_cnt} direct"
                if exp_cnt > 0 or ls_cnt > 0:
                    link_summary += f", {exp_cnt} expanded via {ls_cnt} linkset(s)"
                link_summary += ")"

                if target_url:
                    print(f"  Target: {target_url} ({status_str}{ct_str}{dur_str} | {link_summary})")
            elif target_url:
                print(f"  Target: {target_url}")

            for res in target_results:
                label = _format_expectation_label(res)
                source_badge = _format_source_badge(res.matched_links)

                if res.skipped:
                    print(f"    [⚠ SKIP] {label}: {res.skipped_message}")
                elif res.passed:
                    match_info = f" ({len(res.matched_links)} matched)" if len(res.matched_links) > 1 else ""
                    badge_part = f" {source_badge}" if source_badge else ""
                    print(f"    [✓ PASS] {label}{match_info}{badge_part}")
                else:
                    fail_msg = f" [{res.failure_message}]" if res.failure_message else " [FAILED]"
                    print(f"    [✗ FAIL] {label}{fail_msg}")
                    if res.matched_links:
                        print(f"             (Found {len(res.matched_links)} matching link(s) but expectation criteria not satisfied)")

                should_print_diagram = (
                    diagram_mode == "always"
                    or (diagram_mode == "on-failure" and not res.passed and not res.skipped)
                )
                if should_print_diagram and res.diagram:
                    print(f"\n{res.diagram}\n")

    print(f"{'─' * LINE_WIDTH}")


def print_flat_results(
    results: List[AssertionResult],
    diagram_mode: str = "on-failure",
    detailed: bool = True,
) -> None:
    """Print results line-by-line with optional carrier provenance subline."""
    for res in results:
        status_tag = "✓ PASSED" if res.passed and not res.skipped else ("⚠ SKIPPED" if res.skipped else "✗ FAILED")
        print(f"[{status_tag}] {res.case_name}")

        if detailed and res.passed and res.matched_links:
            source_badge = _format_source_badge(res.matched_links)
            node = res.harvest_node
            dur_str = f" ({node.duration:.3f}s)" if node and getattr(node, "duration", 0) > 0 else ""
            print(f"           ↳ Matched {len(res.matched_links)} link(s) {source_badge}{dur_str}")

        should_print_diagram = (
            diagram_mode == "always"
            or (diagram_mode == "on-failure" and not res.passed and not res.skipped)
        )
        if should_print_diagram and res.diagram:
            print(f"\n{res.diagram}\n")
