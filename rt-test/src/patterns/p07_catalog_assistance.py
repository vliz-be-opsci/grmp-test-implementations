"""
Pattern PT-07: Catalog Assistance for Hostwide Discovery (RT-P07).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional
from urllib.parse import urlparse

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class CatalogAssistancePattern(RTPattern):
    """
    PT-07: Catalog Assistance for Hostwide Discovery.
    Bridges hostwide discovery with API catalogs (/.well-known/api-catalog) and
    specialized sitemaps, delegating large-scale asset discovery to APIs and catalogs.
    """

    pattern_id: ClassVar[str] = "PT-07"
    pattern_name: ClassVar[str] = "Catalog Assistance for Hostwide Discovery"
    pattern_description: ClassVar[str] = (
        "Bridges hostwide discovery with API catalogs (/.well-known/api-catalog), "
        "connecting endpoints, sitemap indices, and service profiles."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P07",
        "P07",
        "PT-7",
        "RT-7",
        "7",
        "catalog-assistance",
        "api-catalog-assistance",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="host",
            required=False,
            description="Root host domain URL (e.g. http://localhost:8080)",
            aliases=["domain", "hostname"],
        ),
        PatternRoleDefinition(
            name="robots_txt",
            required=False,
            description="Robots.txt discovery URL or boolean (defaults to True)",
            aliases=["robots"],
        ),
        PatternRoleDefinition(
            name="sitemap_index",
            required=False,
            description="Main host sitemap index XML URL (e.g. http://localhost:8080/sitemap-index.xml)",
            aliases=["sitemap", "sitemap_xml", "root_sitemap"],
        ),
        PatternRoleDefinition(
            name="api_catalog",
            required=True,
            description="The RFC 9727 API catalog endpoint URI (e.g. /.well-known/api-catalog)",
            aliases=["catalog", "catalog_uri", "registry"],
        ),
        PatternRoleDefinition(
            name="api_catalog_sitemap",
            required=False,
            description="Dedicated API catalog sitemap XML URL (e.g. /.well-known/api-catalog/sitemap-index.xml)",
            aliases=["catalog_sitemap", "api_sitemap"],
        ),
        PatternRoleDefinition(
            name="api_endpoints",
            required=False,
            is_list=True,
            description="List of individual API endpoints (each supporting uri, sitemap, profile, subresources)",
            aliases=["endpoints", "feeds", "services", "apis"],
        ),
        PatternRoleDefinition(
            name="resources",
            required=False,
            is_list=True,
            description="List of sub-resources or dataset records (backward compatibility)",
            aliases=["records", "items", "subresources"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        api_catalog_uri = self.get_role_uri("api_catalog")
        sitemap_index_uri = self.get_role_uri("sitemap_index")
        host_uri = self.get_role_uri("host")

        # 1. Derive host_uri if not explicitly provided
        if not host_uri:
            ref_uri = api_catalog_uri or sitemap_index_uri
            if ref_uri:
                parsed = urlparse(ref_uri)
                if parsed.scheme and parsed.netloc:
                    host_uri = f"{parsed.scheme}://{parsed.netloc}"

        # 2. Derive robots_txt URL
        robots_raw = self.roles.get("robots_txt")
        if robots_raw is None:
            robots_raw = self.roles.get("robots")

        robots_url: Optional[str] = None
        if robots_raw is None or robots_raw is True:
            if host_uri:
                robots_url = f"{host_uri.rstrip('/')}/robots.txt"
        elif isinstance(robots_raw, str):
            val_lower = robots_raw.strip().lower()
            if val_lower == "true":
                if host_uri:
                    robots_url = f"{host_uri.rstrip('/')}/robots.txt"
            elif val_lower != "false":
                robots_url = robots_raw.strip()

        # 3. Derive api_catalog_sitemap if not explicitly specified
        api_catalog_sitemap = self.get_role_uri("api_catalog_sitemap")
        if not api_catalog_sitemap and host_uri:
            api_catalog_sitemap = f"{host_uri.rstrip('/')}/.well-known/api-catalog/sitemap-index.xml"

        # 4. Parse api_endpoints specs
        raw_endpoints = self.get_role_list("api_endpoints")
        endpoint_specs: List[Dict[str, Any]] = []

        for ep in raw_endpoints:
            if isinstance(ep, str):
                ep_uri = ep.strip()
                if not ep_uri:
                    continue
                endpoint_specs.append({
                    "uri": ep_uri,
                    "sitemap": f"{ep_uri.rstrip('/')}/sitemap.xml",
                    "profile": None,
                    "subresources": [],
                })
            elif isinstance(ep, dict):
                ep_uri = (ep.get("uri") or ep.get("href") or ep.get("target") or "").strip()
                if not ep_uri:
                    continue
                sub_sm = ep.get("sitemap") or ep.get("sub_sitemap")
                if not sub_sm:
                    sub_sm = f"{ep_uri.rstrip('/')}/sitemap.xml"

                raw_sub_res = ep.get("subresources") or ep.get("resources") or []
                if isinstance(raw_sub_res, str):
                    raw_sub_res = [raw_sub_res]

                subresources: List[str] = []
                for r in raw_sub_res:
                    r_str = (r if isinstance(r, str) else r.get("uri", r.get("href", ""))).strip()
                    if r_str:
                        subresources.append(r_str)

                endpoint_specs.append({
                    "uri": ep_uri,
                    "sitemap": sub_sm,
                    "profile": ep.get("profile"),
                    "subresources": subresources,
                })

        # Backward compatibility for top-level resources role
        top_resources = self.get_role_list("resources")
        if top_resources and endpoint_specs and not endpoint_specs[0]["subresources"]:
            for r in top_resources:
                r_url = (r if isinstance(r, str) else r.get("uri", r.get("href", ""))).strip()
                if r_url:
                    endpoint_specs[0]["subresources"].append(r_url)

        test_cases: List[TestCaseConfig] = []

        # =========================================================================
        # Pillar 2: Sitemaps Hierarchy (sitemaps.org)
        # =========================================================================

        # 2.1 Robots.txt Sitemap directive
        if robots_url and sitemap_index_uri:
            test_cases.append(
                self.create_test_case(
                    name_suffix="Robots Sitemap Directive",
                    target_urls=[robots_url],
                    relations=[
                        RelationExpectation(
                            rel="item",
                            target=sitemap_index_uri,
                            exists=True,
                        )
                    ],
                )
            )

        # 2.2 Root Sitemap Index Delegation
        if sitemap_index_uri:
            sm_index_expectations: List[RelationExpectation] = []
            if api_catalog_sitemap:
                sm_index_expectations.append(
                    RelationExpectation(
                        rel="item",
                        target=api_catalog_sitemap,
                        exists=True,
                    )
                )
            for ep_spec in endpoint_specs:
                if ep_spec.get("sitemap"):
                    sm_index_expectations.append(
                        RelationExpectation(
                            rel="item",
                            target=ep_spec["sitemap"],
                            exists=True,
                        )
                    )
            if sm_index_expectations:
                test_cases.append(
                    self.create_test_case(
                        name_suffix="Sitemap Index Delegation",
                        target_urls=[sitemap_index_uri],
                        relations=sm_index_expectations,
                    )
                )

        # 2.3 API Catalog Sitemap Binding (rel="self" back to catalog, loc items to endpoints)
        if api_catalog_sitemap:
            cat_sm_expectations = [
                RelationExpectation(
                    rel="self",
                    target=api_catalog_uri,
                    exists=True,
                )
            ]
            for ep_spec in endpoint_specs:
                cat_sm_expectations.append(
                    RelationExpectation(
                        rel="item",
                        target=ep_spec["uri"],
                        exists=True,
                    )
                )
            test_cases.append(
                self.create_test_case(
                    name_suffix="API Catalog Sitemap Binding",
                    target_urls=[api_catalog_sitemap],
                    relations=cat_sm_expectations,
                )
            )

        # =========================================================================
        # Pillar 3: API Catalog (RFC 9727 /.well-known/api-catalog)
        # =========================================================================
        catalog_expectations: List[RelationExpectation] = []
        if api_catalog_sitemap:
            catalog_expectations.append(
                RelationExpectation(
                    rel="alternate",
                    target=api_catalog_sitemap,
                    exists=True,
                )
            )
        for ep_spec in endpoint_specs:
            catalog_expectations.append(
                RelationExpectation(
                    rel="item",
                    target=ep_spec["uri"],
                    exists=True,
                )
            )

        test_cases.append(
            self.create_test_case(
                name_suffix="API Catalog Listing & Alternates",
                target_urls=[api_catalog_uri],
                relations=catalog_expectations,
            )
        )

        # =========================================================================
        # Pillar 1: API Services & Subresources
        # =========================================================================
        for idx, ep_spec in enumerate(endpoint_specs, start=1):
            ep_url = ep_spec["uri"]

            # 1.1 API Endpoint Link Headers / Body
            ep_expectations: List[RelationExpectation] = [
                RelationExpectation(
                    rel="api-catalog",
                    target=api_catalog_uri,
                    exists=True,
                )
            ]
            if ep_spec.get("sitemap"):
                ep_expectations.append(
                    RelationExpectation(
                        rel="alternate",
                        target=ep_spec["sitemap"],
                        exists=True,
                    )
                )
            if ep_spec.get("profile"):
                ep_expectations.append(
                    RelationExpectation(
                        rel="profile",
                        target=ep_spec["profile"],
                        exists=True,
                    )
                )

            test_cases.append(
                self.create_test_case(
                    name_suffix=f"API Endpoint #{idx} [{ep_url}] Context",
                    target_urls=[ep_url],
                    relations=ep_expectations,
                )
            )

            # 1.2 Dedicated API Sub-Sitemap (rel="self" back to endpoint, loc items to subresources)
            if ep_spec.get("sitemap"):
                sub_sm_url = ep_spec["sitemap"]
                sub_sm_expectations = [
                    RelationExpectation(
                        rel="self",
                        target=ep_url,
                        exists=True,
                    )
                ]
                for res_url in ep_spec["subresources"]:
                    sub_sm_expectations.append(
                        RelationExpectation(
                            rel="item",
                            target=res_url,
                            exists=True,
                        )
                    )

                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"API Sub-Sitemap [{sub_sm_url}] Self & Entries",
                        target_urls=[sub_sm_url],
                        relations=sub_sm_expectations,
                    )
                )

            # 1.3 Subresources: Collection Uplink back to API Endpoint
            for r_idx, res_url in enumerate(ep_spec["subresources"], start=1):
                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"Sub-Resource #{r_idx} [{res_url}] Collection Uplink",
                        target_urls=[res_url],
                        relations=[
                            RelationExpectation(
                                rel="collection",
                                target=ep_url,
                                exists=True,
                            )
                        ],
                    )
                )

        return test_cases
