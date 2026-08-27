"""
Pattern PT-02: Profile Composition (RT-P02).
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional

from config.models import RelationExpectation, TestCaseConfig
from .base import PatternRoleDefinition, RTPattern
from .registry import register_pattern


@register_pattern
class ProfileCompositionPattern(RTPattern):
    """
    PT-02: Profile Composition.
    Validates that a resource conforms to a composite profile and its constituent member profiles.
    """

    pattern_id: ClassVar[str] = "PT-02"
    pattern_name: ClassVar[str] = "Profile Composition"
    pattern_description: ClassVar[str] = (
        "Validates composite profiles aggregating member profiles via hasPart, "
        "and ensures direct/inferred conformance on the target resource."
    )
    aliases: ClassVar[List[str]] = [
        "RT-P02",
        "P02",
        "PT-2",
        "RT-2",
        "2",
        "profile-composition",
        "composite-profile",
    ]

    role_definitions: ClassVar[List[PatternRoleDefinition]] = [
        PatternRoleDefinition(
            name="resource",
            required=True,
            description="The resource URI declaring composite profile conformity",
            aliases=["target", "url", "resource_uri", "anchor"],
        ),
        PatternRoleDefinition(
            name="composite_profile",
            required=True,
            description="The composite profile URI",
            aliases=["composite", "profile", "parent_profile", "root_profile"],
        ),
        PatternRoleDefinition(
            name="member_profiles",
            required=True,
            is_list=True,
            description="List of constituent member profile URIs",
            aliases=["members", "parts", "sub_profiles", "has_part"],
        ),
        PatternRoleDefinition(
            name="check_composite",
            required=False,
            description="Whether to harvest the composite profile URI to check hasPart relations",
            aliases=["verify_composite", "check_parent"],
        ),
    ]

    def resolve_test_cases(self) -> List[TestCaseConfig]:
        validation = self.validate_roles()
        validation.raise_for_errors(self.pattern_id)

        resource_uri = self.get_role_uri("resource")
        composite_uri = self.get_role_uri("composite_profile")
        member_profiles = self.get_role_list("member_profiles")

        test_cases: List[TestCaseConfig] = []

        # 1. Conformance expectations on the resource itself
        resource_expectations: List[RelationExpectation] = [
            RelationExpectation(
                rel="profile",
                target=composite_uri,
                exists=True,
            )
        ]

        # Inferred / explicit conformance to each member profile
        for member in member_profiles:
            member_uri = member if isinstance(member, str) else member.get("uri", member.get("href"))
            if member_uri:
                resource_expectations.append(
                    RelationExpectation(
                        rel="profile",
                        target=member_uri,
                        exists=True,
                    )
                )

        test_cases.append(
            self.create_test_case(
                name_suffix="Resource Composite & Member Profile Declarations",
                target_urls=[resource_uri],
                relations=resource_expectations,
            )
        )

        # 2. Composition structure on the composite profile URI if check_composite is enabled
        if self.roles.get("check_composite"):
            comp_expectations: List[RelationExpectation] = []
            for member in member_profiles:
                member_uri = member if isinstance(member, str) else member.get("uri", member.get("href"))
                if member_uri:
                    comp_expectations.append(
                        RelationExpectation(
                            rel="http://schema.org/hasPart",
                            target=member_uri,
                            exists=True,
                        )
                    )
            if comp_expectations:
                test_cases.append(
                    self.create_test_case(
                        name_suffix="Composite Profile Parts",
                        target_urls=[composite_uri],
                        relations=comp_expectations,
                    )
                )

        return test_cases
