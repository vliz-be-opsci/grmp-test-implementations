"""
Pattern PT-06: Hostwide Resource Discovery (RT-P06).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional
from urllib.parse import urljoin

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class HostwideDiscoveryPattern(RTPattern):
    """
    PT-06: Hostwide Resource Discovery.
    Validates automated discovery bootstrapping from /robots.txt -> sitemaps (with <rs:ln> annotations) -> resources.
    """

    pattern_id: ClassVar[str] = "PT-06"
    pattern_name: ClassVar[str] = "Hostwide Resource Discovery"
    pattern_description: ClassVar[str] = (
        "Bootstraps automated discovery across an entire host: robots.txt declares sitemaps, "
        "sitemaps list resource URLs with typed link annotations, and resources provide signposting."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P06",
        "P06",
        "PT-6",
        "RT-6",
        "6",
        "hostwide-discovery",
        "robots-sitemap",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="host",
            required=True,
            description="The root host / origin URL (e.g. http://localhost:8080/)",
            aliases=["hostname", "domain", "base_url", "origin"],
        ),
        PatternRoleDefinition(
            name="robots_txt",
            required=False,
            description="The robots.txt URL (defaults to <host>/robots.txt)",
            aliases=["robots", "robots_url"],
        ),
        PatternRoleDefinition(
            name="sitemap",
            required=False,
            description="The expected primary sitemap XML URL",
            aliases=["sitemap_url", "sitemap_xml"],
        ),
        PatternRoleDefinition(
            name="resources",
            required=False,
            is_list=True,
            description="List of sample resource URIs expected to be discovered",
            aliases=["sample_resources", "records", "locs"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        host_uri = self.get_role_uri("host") or ""
        robots_uri = self.get_role_uri("robots_txt") or urljoin(host_uri, "/robots.txt")
        sitemap_uri = self.get_role_uri("sitemap")
        resources = self.get_role_list("resources")

        test_cases: List[TestCaseConfig] = []

        # 1. Robots.txt discovery test
        robots_expectations: List[RelationExpectation] = []
        if sitemap_uri:
            # robots.txt parses sitemap directives as link relations or can verify reachability
            pass

        test_cases.append(
            self.create_test_case(
                name_suffix="Robots.txt Reachability & Discovery",
                target_urls=[robots_uri],
                relations=robots_expectations,
            )
        )

        # 2. Sitemap test case
        if sitemap_uri:
            test_cases.append(
                self.create_test_case(
                    name_suffix="Sitemap XML Processing",
                    target_urls=[sitemap_uri],
                    relations=[],
                )
            )

        # 3. Discovered sample resources test
        resource_urls = [r if isinstance(r, str) else r.get("uri", r.get("href")) for r in resources if r]
        if resource_urls:
            test_cases.append(
                self.create_test_case(
                    name_suffix="Sample Resources Harvest",
                    target_urls=resource_urls,
                    relations=[],
                )
            )

        return test_cases
