"""
Pattern PT-07: Catalog Assistance for Hostwide Discovery (RT-P07).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class CatalogAssistancePattern(RTPattern):
    """
    PT-07: Catalog Assistance for Hostwide Discovery.
    Validates API catalog (/.well-known/api-catalog) integration with sitemaps,
    listing feeds/endpoints and declaring service profiles.
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
            name="api_catalog",
            required=True,
            description="The API catalog endpoint URI (e.g. /.well-known/api-catalog)",
            aliases=["catalog", "catalog_uri", "registry"],
        ),
        PatternRoleDefinition(
            name="api_catalog_sitemap",
            required=False,
            description="The API catalog sitemap XML URI",
            aliases=["catalog_sitemap", "api_sitemap"],
        ),
        PatternRoleDefinition(
            name="sitemap_index",
            required=False,
            description="Main host sitemap index XML URL",
            aliases=["sitemap", "sitemap_xml"],
        ),
        PatternRoleDefinition(
            name="api_endpoints",
            required=False,
            is_list=True,
            description="List of individual API endpoints (each optionally with profile/sub_sitemap)",
            aliases=["endpoints", "feeds", "services", "apis"],
        ),
        PatternRoleDefinition(
            name="resources",
            required=False,
            is_list=True,
            description="List of sub-resources or dataset records",
            aliases=["records", "items"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        api_catalog_uri = self.get_role_uri("api_catalog")
        api_catalog_sitemap = self.get_role_uri("api_catalog_sitemap")
        raw_endpoints = self.get_role_list("api_endpoints")

        test_cases: List[TestCaseConfig] = []

        # 1. API Catalog Expectations
        catalog_expectations: List[RelationExpectation] = []
        endpoint_specs: List[Dict[str, Any]] = []

        for ep in raw_endpoints:
            if isinstance(ep, str):
                ep_spec = {"uri": ep.strip(), "profile": None, "sub_sitemap": None}
            elif isinstance(ep, dict):
                ep_spec = {
                    "uri": ep.get("uri") or ep.get("href") or ep.get("target"),
                    "profile": ep.get("profile"),
                    "sub_sitemap": ep.get("sub_sitemap") or ep.get("sitemap"),
                }
            else:
                continue

            if ep_spec["uri"]:
                endpoint_specs.append(ep_spec)
                catalog_expectations.append(
                    RelationExpectation(
                        rel="item",
                        target=ep_spec["uri"],
                        exists=True,
                    )
                )

        if api_catalog_sitemap:
            catalog_expectations.append(
                RelationExpectation(
                    rel="alternate",
                    target=api_catalog_sitemap,
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

        # 2. Expectations on each API endpoint
        for idx, ep_spec in enumerate(endpoint_specs, start=1):
            ep_url = ep_spec["uri"]
            ep_expectations: List[RelationExpectation] = [
                RelationExpectation(
                    rel="api-catalog",
                    target=api_catalog_uri,
                    exists=True,
                )
            ]
            if ep_spec["profile"]:
                ep_expectations.append(
                    RelationExpectation(
                        rel="profile",
                        target=ep_spec["profile"],
                        exists=True,
                    )
                )
            if ep_spec["sub_sitemap"]:
                ep_expectations.append(
                    RelationExpectation(
                        rel="alternate",
                        target=ep_spec["sub_sitemap"],
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

            # 3. Sub-sitemap expectations (rel="self" to API endpoint and rel="api-catalog" to root catalog)
            if ep_spec["sub_sitemap"]:
                sub_sitemap_url = ep_spec["sub_sitemap"]
                sub_sitemap_expectations = [
                    RelationExpectation(
                        rel="self",
                        target=ep_url,
                        exists=True,
                    ),
                    RelationExpectation(
                        rel="api-catalog",
                        target=api_catalog_uri,
                        exists=True,
                    ),
                ]
                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"API Sub-Sitemap [{sub_sitemap_url}] Self & Catalog Links",
                        target_urls=[sub_sitemap_url],
                        relations=sub_sitemap_expectations,
                    )
                )

        # 4. Granular resources expectations (rel="collection" back to API endpoint)
        raw_resources = self.get_role_list("resources")
        if raw_resources and endpoint_specs:
            primary_ep = endpoint_specs[0]["uri"]
            for r_idx, res in enumerate(raw_resources, start=1):
                r_url = res if isinstance(res, str) else res.get("uri", res.get("href"))
                if r_url:
                    res_expectations = [
                        RelationExpectation(
                            rel="collection",
                            target=primary_ep,
                            exists=True,
                        )
                    ]
                    test_cases.append(
                        self.create_test_case(
                            name_suffix=f"Sub-Resource #{r_idx} [{r_url}] Collection Uplink",
                            target_urls=[r_url],
                            relations=res_expectations,
                        )
                    )

        return test_cases
