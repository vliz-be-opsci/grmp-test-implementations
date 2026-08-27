"""
Pattern PT-03: Content Negotiation Menu (RT-P03).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class ContentNegotiationMenuPattern(RTPattern):
    """
    PT-03: Content Negotiation Menu.
    Validates representation variants and restores identity anchor via rel="self" after conneg redirects.
    """

    pattern_id: ClassVar[str] = "PT-03"
    pattern_name: ClassVar[str] = "Content Negotiation Menu"
    pattern_description: ClassVar[str] = (
        "Exposes available representation variants via rel=alternate and ensures variants link "
        "back to the conceptual identity resource via rel=self."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P03",
        "P03",
        "PT-3",
        "RT-3",
        "3",
        "conneg-menu",
        "content-negotiation-menu",
        "variant-menu",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="concept",
            required=True,
            description="The central conceptual resource / identity anchor URI",
            aliases=["self", "concept_uri", "identity", "identity_uri", "target", "resource"],
        ),
        PatternRoleDefinition(
            name="variants",
            required=True,
            is_list=True,
            description="List of representation variant URIs or objects with type/profile metadata",
            aliases=["representations", "alternate", "alternates", "variant_list"],
        ),
        PatternRoleDefinition(
            name="variant_menu",
            required=False,
            description="The external variant menu linkset URI",
            aliases=["linkset", "menu", "linkset_uri"],
        ),
        PatternRoleDefinition(
            name="check_variants",
            required=False,
            description="Whether to harvest each variant to verify rel=self back to concept (default: True)",
            aliases=["verify_variants", "test_variants"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        concept_uri = self.get_role_uri("concept")
        variant_menu_uri = self.get_role_uri("variant_menu")
        raw_variants = self.get_role_list("variants")
        check_variants = self.roles.get("check_variants", True)

        test_cases: List[TestCaseConfig] = []

        # 1. Expectations on the conceptual identity resource
        concept_expectations: List[RelationExpectation] = []
        variant_specs: List[Dict[str, Any]] = []

        for v in raw_variants:
            if isinstance(v, str):
                v_spec = {"uri": v.strip(), "type": None, "profile": None}
            elif isinstance(v, dict):
                v_spec = {
                    "uri": v.get("uri") or v.get("href") or v.get("target"),
                    "type": v.get("type") or v.get("media_type"),
                    "profile": v.get("profile"),
                }
            else:
                continue

            if v_spec["uri"]:
                variant_specs.append(v_spec)
                concept_expectations.append(
                    RelationExpectation(
                        rel="alternate",
                        target=v_spec["uri"],
                        type=v_spec["type"],
                        profile=v_spec["profile"],
                        exists=True,
                    )
                )

        if variant_menu_uri:
            concept_expectations.append(
                RelationExpectation(
                    rel="linkset",
                    target=variant_menu_uri,
                    exists=True,
                )
            )

        test_cases.append(
            self.create_test_case(
                name_suffix="Conceptual Resource Alternates",
                target_urls=[concept_uri],
                relations=concept_expectations,
            )
        )

        # 2. Expectations on each variant representation (rel="self" back to concept)
        if check_variants and variant_specs:
            for idx, v_spec in enumerate(variant_specs, start=1):
                v_url = v_spec["uri"]
                variant_expectations = [
                    RelationExpectation(
                        rel="self",
                        target=concept_uri,
                        exists=True,
                    )
                ]
                if variant_menu_uri:
                    variant_expectations.append(
                        RelationExpectation(
                            rel="linkset",
                            target=variant_menu_uri,
                            exists=True,
                        )
                    )

                test_cases.append(
                    self.create_test_case(
                        name_suffix=f"Variant #{idx} [{v_url}] Self Restoration",
                        target_urls=[v_url],
                        relations=variant_expectations,
                    )
                )

        return test_cases
