"""
Pattern PT-05: Subsetting API (RT-P05).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class SubsettingAPIPattern(RTPattern):
    """
    PT-05: Subsetting API.
    Validates dynamic API and subsetting fragment endpoints, linking to dataset PID (cite-as),
    composition hierarchy (item/collection), API catalog, and service metadata.
    """

    pattern_id: ClassVar[str] = "PT-05"
    pattern_name: ClassVar[str] = "Subsetting API"
    pattern_description: ClassVar[str] = (
        "Validates subsetting/dynamic API endpoints, linking queries/fragments to base APIs and datasets, "
        "and registering service descriptions."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P05",
        "P05",
        "PT-5",
        "RT-5",
        "5",
        "subsetting-api",
        "dynamic-api",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="dataset",
            required=True,
            description="The underlying dataset PID or identifier URI",
            aliases=["pid", "dataset_uri", "dataset_pid", "doi"],
        ),
        PatternRoleDefinition(
            name="base_api",
            required=True,
            description="The main/base API service endpoint URI",
            aliases=["api", "api_uri", "endpoint", "service"],
        ),
        PatternRoleDefinition(
            name="fragment_api",
            required=False,
            description="Subsetting / query / fragment API endpoint URI",
            aliases=["subset_api", "fragment", "subset", "query_api"],
        ),
        PatternRoleDefinition(
            name="api_catalog",
            required=False,
            description="API catalog / registry endpoint URI",
            aliases=["catalog", "catalog_uri", "registry"],
        ),
        PatternRoleDefinition(
            name="service_desc",
            required=False,
            description="Machine-readable API service description (OpenAPI, etc.)",
            aliases=["openapi", "swagger", "wsdl", "desc"],
        ),
        PatternRoleDefinition(
            name="service_doc",
            required=False,
            description="Human documentation for the API",
            aliases=["documentation", "doc", "service_documentation"],
        ),
        PatternRoleDefinition(
            name="service_meta",
            required=False,
            description="Service capabilities or metadata endpoint",
            aliases=["metadata", "meta"],
        ),
        PatternRoleDefinition(
            name="status",
            required=False,
            description="Service health / status endpoint",
            aliases=["health", "status_uri"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        dataset_uri = self.get_role_uri("dataset")
        base_api_uri = self.get_role_uri("base_api")
        fragment_api_uri = self.get_role_uri("fragment_api")
        api_catalog_uri = self.get_role_uri("api_catalog")
        service_desc_uri = self.get_role_uri("service_desc")
        service_doc_uri = self.get_role_uri("service_doc")
        service_meta_uri = self.get_role_uri("service_meta")
        status_uri = self.get_role_uri("status")

        test_cases: List[TestCaseConfig] = []

        # 1. Base API expectations
        base_expectations: List[RelationExpectation] = [
            RelationExpectation(
                rel="cite-as",
                target=dataset_uri,
                exists=True,
            )
        ]

        if fragment_api_uri:
            base_expectations.append(
                RelationExpectation(
                    rel="item",
                    target=fragment_api_uri,
                    exists=True,
                )
            )

        if api_catalog_uri:
            base_expectations.append(
                RelationExpectation(
                    rel="api-catalog",
                    target=api_catalog_uri,
                    exists=True,
                )
            )

        if service_desc_uri:
            base_expectations.append(
                RelationExpectation(
                    rel="service-desc",
                    target=service_desc_uri,
                    exists=True,
                )
            )

        if service_doc_uri:
            base_expectations.append(
                RelationExpectation(
                    rel="service-doc",
                    target=service_doc_uri,
                    exists=True,
                )
            )

        if service_meta_uri:
            base_expectations.append(
                RelationExpectation(
                    rel="service-meta",
                    target=service_meta_uri,
                    exists=True,
                )
            )

        if status_uri:
            base_expectations.append(
                RelationExpectation(
                    rel="status",
                    target=status_uri,
                    exists=True,
                )
            )

        test_cases.append(
            self.create_test_case(
                name_suffix="Base API Metadata & Composition",
                target_urls=[base_api_uri],
                relations=base_expectations,
            )
        )

        # 2. Fragment API expectations (if defined)
        if fragment_api_uri:
            fragment_expectations = [
                RelationExpectation(
                    rel="collection",
                    target=base_api_uri,
                    exists=True,
                ),
                RelationExpectation(
                    rel="cite-as",
                    target=dataset_uri,
                    exists=True,
                ),
            ]
            test_cases.append(
                self.create_test_case(
                    name_suffix="Fragment API Collection & Citation",
                    target_urls=[fragment_api_uri],
                    relations=fragment_expectations,
                )
            )

        return test_cases
