"""
Pattern PT-06: Hostwide Resource Discovery (RT-P06).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional
from urllib.parse import urljoin

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern



def _normalize_uri_list(val: Any) -> List[str]:
    """Helper to convert a string, dict with uri/href, or list into a list of clean URI strings."""
    if val is None:
        return []
    if isinstance(val, list):
        res = []
        for item in val:
            if isinstance(item, str) and item.strip():
                res.append(item.strip())
            elif isinstance(item, dict):
                u = item.get("uri") or item.get("href") or item.get("url")
                if u and str(u).strip():
                    res.append(str(u).strip())
        return res
    if isinstance(val, dict):
        u = val.get("uri") or val.get("href") or val.get("url")
        return [str(u).strip()] if u and str(u).strip() else []
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


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
            description="Boolean (default true) to check <host>/robots.txt, false to skip, or a custom robots.txt URL",
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
            description="List of resource URIs or indented objects with uri, linkset, alternates, and profile",
            aliases=["sample_resources", "records", "locs"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        host_uri = self.get_role_uri("host") or ""
        sitemap_uri = self.get_role_uri("sitemap")
        raw_resources = self.get_role_list("resources")

        # Determine robots.txt behavior (default true)
        robots_raw = self.roles.get("robots_txt")
        if robots_raw is None:
            robots_raw = True

        robots_enabled = True
        robots_uri: Optional[str] = None

        if isinstance(robots_raw, bool):
            robots_enabled = robots_raw
            robots_uri = urljoin(host_uri, "/robots.txt") if robots_enabled else None
        elif isinstance(robots_raw, str):
            val_lower = robots_raw.strip().lower()
            if val_lower in ("false", "no", "0"):
                robots_enabled = False
                robots_uri = None
            elif val_lower in ("true", "yes", "1"):
                robots_enabled = True
                robots_uri = urljoin(host_uri, "/robots.txt")
            else:
                robots_enabled = True
                robots_uri = robots_raw.strip()
        elif isinstance(robots_raw, dict):
            robots_enabled = True
            robots_uri = robots_raw.get("uri") or robots_raw.get("href") or urljoin(host_uri, "/robots.txt")
        else:
            robots_enabled = bool(robots_raw)
            robots_uri = urljoin(host_uri, "/robots.txt") if robots_enabled else None

        test_cases: List[TestCaseConfig] = []

        # 1. Robots.txt discovery test
        if robots_enabled and robots_uri:
            robots_expectations: List[RelationExpectation] = []
            if sitemap_uri:
                robots_expectations.append(
                    RelationExpectation(
                        rel="item",
                        target=sitemap_uri,
                        exists=True,
                    )
                )

            test_cases.append(
                self.create_test_case(
                    name_suffix="Robots.txt Reachability & Discovery",
                    target_urls=[robots_uri],
                    relations=robots_expectations,
                )
            )

        # Parse indented resources
        resource_specs: List[Dict[str, Any]] = []
        for r in raw_resources:
            if isinstance(r, str) and r.strip():
                resource_specs.append({
                    "uri": r.strip(),
                    "linksets": [],
                    "alternates": [],
                    "profiles": [],
                })
            elif isinstance(r, dict):
                r_uri = (r.get("uri") or r.get("href") or r.get("url") or r.get("loc") or "").strip()
                if not r_uri:
                    continue
                r_linksets = _normalize_uri_list(r.get("linkset") or r.get("linksets"))
                r_alternates = _normalize_uri_list(r.get("alternate") or r.get("alternates"))
                r_profiles = _normalize_uri_list(r.get("profile") or r.get("profiles"))
                resource_specs.append({
                    "uri": r_uri,
                    "linksets": r_linksets,
                    "alternates": r_alternates,
                    "profiles": r_profiles,
                })

        # 2. Sitemap test case
        if sitemap_uri:
            sitemap_expectations: List[RelationExpectation] = []
            for spec in resource_specs:
                r_uri = spec["uri"]
                sitemap_expectations.append(
                    RelationExpectation(
                        rel="item",
                        target=r_uri,
                        exists=True,
                    )
                )
                for ls in spec["linksets"]:
                    sitemap_expectations.append(
                        RelationExpectation(
                            rel="linkset",
                            anchor=r_uri,
                            target=ls,
                            exists=True,
                        )
                    )
                for alt in spec["alternates"]:
                    sitemap_expectations.append(
                        RelationExpectation(
                            rel="alternate",
                            anchor=r_uri,
                            target=alt,
                            exists=True,
                        )
                    )
                for prof in spec["profiles"]:
                    sitemap_expectations.append(
                        RelationExpectation(
                            rel="profile",
                            anchor=r_uri,
                            target=prof,
                            exists=True,
                        )
                    )

            test_cases.append(
                self.create_test_case(
                    name_suffix="Sitemap XML Processing",
                    target_urls=[sitemap_uri],
                    relations=sitemap_expectations,
                )
            )

        # 3. Discovered sample resources test
        simple_resource_urls: List[str] = []
        for spec in resource_specs:
            r_uri = spec["uri"]
            has_nested = bool(spec["linksets"] or spec["alternates"] or spec["profiles"])
            if has_nested:
                r_expectations: List[RelationExpectation] = []
                for ls in spec["linksets"]:
                    r_expectations.append(
                        RelationExpectation(
                            rel="linkset",
                            target=ls,
                            exists=True,
                        )
                    )
                for alt in spec["alternates"]:
                    r_expectations.append(
                        RelationExpectation(
                            rel="alternate",
                            target=alt,
                            exists=True,
                        )
                    )
                for prof in spec["profiles"]:
                    r_expectations.append(
                        RelationExpectation(
                            rel="profile",
                            target=prof,
                            exists=True,
                        )
                    )
                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"Resource [{r_uri}] Discovery & Links",
                        target_urls=[r_uri],
                        relations=r_expectations,
                    )
                )
            else:
                simple_resource_urls.append(r_uri)

        if simple_resource_urls:
            test_cases.append(
                self.create_test_case(
                    name_suffix="Sample Resources Harvest",
                    target_urls=simple_resource_urls,
                    relations=[],
                )
            )

        # 4. Linkset consistency test cases
        seen_linksets = set()
        for spec in resource_specs:
            r_uri = spec["uri"]
            for ls in spec["linksets"]:
                if (r_uri, ls) in seen_linksets:
                    continue
                seen_linksets.add((r_uri, ls))

                ls_expectations: List[RelationExpectation] = []
                for alt in spec["alternates"]:
                    ls_expectations.append(
                        RelationExpectation(
                            rel="alternate",
                            anchor=r_uri,
                            target=alt,
                            exists=True,
                        )
                    )
                for prof in spec["profiles"]:
                    ls_expectations.append(
                        RelationExpectation(
                            rel="profile",
                            anchor=r_uri,
                            target=prof,
                            exists=True,
                        )
                    )

                ls_case = self.create_test_case(
                    name_suffix=f"Resource Linkset [{ls}] Alternate Consistency",
                    target_urls=[ls],
                    relations=ls_expectations,
                )
                ls_case.expand_linksets = False
                test_cases.append(ls_case)

        return test_cases
